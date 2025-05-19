import os
import shutil
import logging
import threading
import time
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from werkzeug.utils import secure_filename

from . import mail_bp
from models import db, Email, EmailAttachment, Order, AdminUser, UploadedFile
from app.admin.routes import admin_required, login_required
from app import csrf
from .processor import MailProcessor

# 获取日志记录器
logger = logging.getLogger(__name__)

# 邮件检查线程
mail_thread = None
stop_thread = False

def mail_check_task(app, interval=300):
    """后台任务：定期检查邮件"""
    global stop_thread
    
    with app.app_context():
        logger.info("邮件检查线程启动")
        
        while not stop_thread:
            try:
                # 获取邮箱配置
                host = app.config.get('MAIL_HOST')
                port = app.config.get('MAIL_PORT')
                username = app.config.get('MAIL_USERNAME')
                password = app.config.get('MAIL_PASSWORD')
                mailbox = app.config.get('MAIL_FOLDER', 'INBOX')
                
                if all([host, port, username, password]):
                    logger.info("开始自动检查邮件...")
                    processor = MailProcessor(host, port, username, password, mailbox)
                    emails = processor.fetch_emails(limit=10, only_unread=True)
                    if emails:
                        logger.info(f"自动获取了 {len(emails)} 封新邮件")
                    else:
                        logger.info("没有新邮件")
                
                # 等待下一次检查
                for _ in range(interval):
                    if stop_thread:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"自动检查邮件时出错: {str(e)}")
                # 出错后等待30秒再重试
                for _ in range(30):
                    if stop_thread:
                        break
                    time.sleep(1)

def start_mail_thread(app):
    """启动邮件检查线程"""
    global mail_thread, stop_thread
    
    # 如果线程已存在且在运行，则不重复启动
    if mail_thread and mail_thread.is_alive():
        return
    
    # 重置停止标志
    stop_thread = False
    
    # 创建并启动线程
    interval = app.config.get('MAIL_CHECK_INTERVAL', 300)
    mail_thread = threading.Thread(target=mail_check_task, args=(app, interval))
    mail_thread.daemon = True
    mail_thread.start()
    logger.info("邮件检查线程已启动")

def stop_mail_thread():
    """停止邮件检查线程"""
    global stop_thread
    stop_thread = True
    logger.info("已发送停止邮件检查线程的信号")

@mail_bp.route('/')
@admin_required
def index():
    """邮件管理首页"""
    # 获取未处理和已处理的邮件
    unprocessed_emails = Email.query.filter_by(processed=False).order_by(Email.received_at.desc()).all()
    processed_emails = Email.query.filter_by(processed=True).order_by(Email.received_at.desc()).limit(20).all()
    
    # 获取系统中的所有用户（用于分配任务）
    users = AdminUser.query.all()
    
    # 获取当前邮箱配置
    mail_config = {
        'host': current_app.config.get('MAIL_HOST'),
        'port': current_app.config.get('MAIL_PORT'),
        'username': current_app.config.get('MAIL_USERNAME'),
        'folder': current_app.config.get('MAIL_FOLDER')
    }
    
    return render_template('mail/index.html', 
                          unprocessed_emails=unprocessed_emails,
                          processed_emails=processed_emails,
                          users=users,
                          mail_config=mail_config)

@mail_bp.route('/fetch', methods=['POST'])
@admin_required
@csrf.exempt
def fetch_emails():
    """手动获取邮件"""
    try:
        # 从配置获取邮箱信息
        host = current_app.config.get('MAIL_HOST')
        port = current_app.config.get('MAIL_PORT')
        username = current_app.config.get('MAIL_USERNAME')
        password = current_app.config.get('MAIL_PASSWORD')
        mailbox = current_app.config.get('MAIL_FOLDER', 'INBOX')
        
        if not all([host, port, username, password]):
            return jsonify({'success': False, 'message': '邮箱配置不完整，请先完成配置'})
        
        # 创建邮件处理器并获取邮件
        processor = MailProcessor(host, port, username, password, mailbox)
        emails = processor.fetch_emails(limit=10, only_unread=True)
        
        if emails:
            return jsonify({'success': True, 'message': f'成功获取 {len(emails)} 封新邮件'})
        else:
            return jsonify({'success': True, 'message': '没有发现新邮件'})
    
    except Exception as e:
        logger.error(f"获取邮件时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'获取邮件时出错: {str(e)}'})

@mail_bp.route('/assign', methods=['POST'])
@admin_required
@csrf.exempt
def assign_email():
    """分配邮件任务"""
    email_id = request.form.get('email_id')
    user_id = request.form.get('user_id')
    note = request.form.get('note', '')
    
    if not email_id or not user_id:
        return jsonify({'success': False, 'message': '邮件ID和用户ID不能为空'})
    
    try:
        # 查找邮件和用户
        email_obj = Email.query.get(email_id)
        user = AdminUser.query.get(user_id)
        
        if not email_obj:
            return jsonify({'success': False, 'message': '找不到该邮件'})
            
        if not user:
            return jsonify({'success': False, 'message': '找不到该用户'})
        
        # 检查邮件是否已经被分配过
        if email_obj.processed:
            # 如果已处理，检查是否已有关联订单
            existing_order = Order.query.filter_by(email_id=email_obj.id).first()
            if existing_order:
                return jsonify({
                    'success': False, 
                    'message': f'该邮件已被分配为订单 #{existing_order.order_number}'
                })
        
        # 将该用户的所有订单设为非活跃
        Order.query.filter_by(user_id=user.id).update({Order.is_active: False})
        
        # 创建新订单
        order_note = f"邮件任务: {email_obj.subject}"
        if note:
            order_note += f" - {note}"
            
        new_order = Order(
            order_number=Order.generate_order_number(),
            status=Order.STATUS_PENDING,
            is_active=False,  # 设置新订单为非活跃状态（根据需求更改）
            note=order_note,
            user_id=user.id,
            email_id=email_obj.id  # 关联邮件和订单
        )
        db.session.add(new_order)
        db.session.flush()  # 获取ID但不提交
        
        # 关联邮件和用户
        email_obj.assigned_to = user.id
        
        # 将附件复制到订单目录
        order_uploads_dir = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'uploads', new_order.order_number)
        os.makedirs(order_uploads_dir, exist_ok=True)
        
        # 清空当前工作目录，防止用户当前活跃订单的文件混入
        for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"分配邮件前清理工作目录: 删除文件 {filename}")
                except Exception as e:
                    logger.error(f"清理工作目录文件失败: {filename}, 错误: {str(e)}")
        
        # 如果有附件，将邮件附件复制到用户的工作空间
        for attachment in email_obj.attachments:
            if os.path.exists(attachment.file_path):
                # 生成唯一文件名
                import uuid
                unique_id = uuid.uuid4().hex[:8]
                filename = f"{unique_id}_{attachment.filename}"
                
                # 复制到上传目录
                dest_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                try:
                    shutil.copy2(attachment.file_path, dest_path)
                    
                    # 同时复制到订单存档目录
                    archive_path = os.path.join(order_uploads_dir, filename)
                    shutil.copy2(attachment.file_path, archive_path)
                    
                    # 添加文件记录到数据库
                    uploaded_file = UploadedFile(
                        filename=filename,
                        original_filename=attachment.filename,
                        file_path=dest_path,
                        file_size=attachment.file_size,
                        file_type=attachment.file_type,
                        file_hash=attachment.file_hash,
                        order_id=new_order.id
                    )
                    db.session.add(uploaded_file)
                    logger.info(f"已将附件 {attachment.filename} 复制到订单 {new_order.order_number}")
                except Exception as e:
                    logger.error(f"复制附件时出错: {str(e)}")
        
        # 清理不再需要的邮件附件目录
        try:
            # 删除邮件附件目录中已经复制过的文件
            for attachment in email_obj.attachments:
                if os.path.exists(attachment.file_path):
                    try:
                        os.remove(attachment.file_path)
                        logger.info(f"已删除邮件附件临时文件: {attachment.file_path}")
                    except Exception as e:
                        logger.error(f"删除邮件附件临时文件时出错: {str(e)}")
            
            # 尝试删除邮件附件目录
            attachment_dir = os.path.dirname(email_obj.attachments[0].file_path) if email_obj.attachments else None
            if attachment_dir and os.path.exists(attachment_dir):
                try:
                    # 检查目录是否为空
                    if not os.listdir(attachment_dir):
                        shutil.rmtree(attachment_dir)
                        logger.info(f"已删除空的邮件附件目录: {attachment_dir}")
                except Exception as e:
                    logger.error(f"删除邮件附件目录时出错: {str(e)}")
        except Exception as e:
            logger.error(f"清理邮件附件时出错: {str(e)}")
        
        # 邮件标记为已处理
        email_obj.processed = True
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'任务已分配给用户 {user.username}，订单号: {new_order.order_number}'
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"分配邮件时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'分配邮件时出错: {str(e)}'})

@mail_bp.route('/view/<int:email_id>')
@admin_required
def view_email(email_id):
    """查看邮件详情"""
    email_obj = Email.query.get_or_404(email_id)
    users = AdminUser.query.all()
    return render_template('mail/view.html', email=email_obj, users=users)

@mail_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """邮件设置页面"""
    if request.method == 'POST':
        # 获取表单数据
        mail_host = request.form.get('mail_host')
        mail_port = request.form.get('mail_port', 993)
        mail_username = request.form.get('mail_username')
        mail_password = request.form.get('mail_password')
        mail_folder = request.form.get('mail_folder', 'INBOX')
        mail_check_interval = request.form.get('mail_check_interval', 300)
        
        # 更新配置
        current_app.config['MAIL_HOST'] = mail_host
        current_app.config['MAIL_PORT'] = int(mail_port)
        current_app.config['MAIL_USERNAME'] = mail_username
        current_app.config['MAIL_PASSWORD'] = mail_password
        current_app.config['MAIL_FOLDER'] = mail_folder
        current_app.config['MAIL_CHECK_INTERVAL'] = int(mail_check_interval)
        
        # 测试连接
        processor = MailProcessor(mail_host, int(mail_port), mail_username, mail_password, mail_folder)
        if processor.connect():
            # 连接成功，重启邮件检查线程
            stop_mail_thread()
            start_mail_thread(current_app._get_current_object())
            flash('邮箱配置已更新，连接测试成功')
        else:
            flash('邮箱配置已更新，但连接测试失败，请检查配置', 'error')
            
        return redirect(url_for('mail.settings'))
    
    # 获取当前配置
    mail_host = current_app.config.get('MAIL_HOST')
    mail_port = current_app.config.get('MAIL_PORT')
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_folder = current_app.config.get('MAIL_FOLDER')
    mail_check_interval = current_app.config.get('MAIL_CHECK_INTERVAL')
    
    return render_template('mail/settings.html',
                          mail_host=mail_host,
                          mail_port=mail_port,
                          mail_username=mail_username,
                          mail_folder=mail_folder,
                          mail_check_interval=mail_check_interval)

@mail_bp.route('/test_connection', methods=['POST'])
@admin_required
@csrf.exempt
def test_connection():
    """测试邮箱连接"""
    try:
        # 获取表单数据
        mail_host = request.form.get('mail_host')
        mail_port = request.form.get('mail_port', 993)
        mail_username = request.form.get('mail_username')
        mail_password = request.form.get('mail_password')
        mail_folder = request.form.get('mail_folder', 'INBOX')
        
        # 测试连接
        processor = MailProcessor(mail_host, int(mail_port), mail_username, mail_password, mail_folder)
        if processor.connect():
            return jsonify({'success': True, 'message': '连接成功'})
        else:
            return jsonify({'success': False, 'message': '连接失败，请检查配置'})
    
    except Exception as e:
        logger.error(f"测试邮箱连接时出错: {str(e)}")
        return jsonify({'success': False, 'message': f'连接测试出错: {str(e)}'}) 