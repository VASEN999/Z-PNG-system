import os
import shutil
import json
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app, session
from werkzeug.utils import secure_filename

from . import orders_bp
from models import db, Order, UploadedFile, ConvertedFile, AdminUser
from app import csrf  # 导入从app/__init__.py创建的csrf对象
from app.admin.routes import login_required  # 导入登录验证装饰器

# 获取日志记录器
logger = logging.getLogger(__name__)

@orders_bp.route('/')
@login_required
def index():
    """订单管理首页"""
    # 获取当前用户
    current_user = AdminUser.query.get(session['admin_id'])
    
    # 从请求参数获取筛选条件
    status_filter = request.args.get('status')
    creator_filter = request.args.get('creator')
    note_search = request.args.get('note_search')
    
    # 构建查询
    query = Order.query
    
    # 应用筛选条件
    if status_filter:
        query = query.filter(Order.status == status_filter)
    
    if creator_filter:
        query = query.filter(Order.user_id == int(creator_filter))
    
    # 添加备注搜索功能
    if note_search:
        query = query.filter(Order.note.ilike(f'%{note_search}%'))
    
    # 如果是管理员，显示所有订单，否则只显示用户自己的订单
    if current_user and current_user.is_admin:
        # 管理员可以看到所有订单，只应用筛选条件
        pass
    else:
        # 非管理员只能看到自己的订单
        query = query.filter_by(user_id=session['admin_id'])
    
    # 获取排序后的订单列表    
    orders = query.order_by(Order.created_at.desc()).all()
    
    # 获取所有用户列表（用于创建人筛选下拉框）
    users = AdminUser.query.all()
    
    # 如果筛选了创建人，获取创建人名称用于显示在筛选标签中
    creator_name = None
    if creator_filter:
        creator = AdminUser.query.get(int(creator_filter))
        if creator:
            creator_name = creator.username
        
    return render_template('orders/index.html', 
                          orders=orders,
                          users=users,
                          creator_name=creator_name,
                          current_user=current_user)

@orders_bp.route('/create', methods=['POST'])
@csrf.exempt  # 豁免CSRF保护
@login_required
def create_order():
    """创建新订单"""
    # 获取当前用户ID
    current_user_id = session.get('admin_id')
    
    # 创建新订单
    new_order = Order(
        order_number=Order.generate_order_number(),
        is_active=True,  # 保留此字段以兼容现有代码
        status=Order.STATUS_PENDING,  # 新订单默认为待处理状态
        user_id=current_user_id  # 设置订单的用户ID
    )
    
    # 添加备注信息（如果提供）
    if 'note' in request.form and request.form['note'].strip():
        new_order.note = request.form['note'].strip()
    
    db.session.add(new_order)
    
    # 将该用户的所有订单设为非活跃
    Order.query.filter_by(user_id=current_user_id).update({Order.is_active: False})
    
    # 将新订单设为活跃
    new_order.is_active = True
    
    # 存档当前工作目录中的文件
    # 找到当前用户的活跃订单（在更新之前）
    current_active = Order.query.filter_by(is_active=True, user_id=current_user_id).first()
    
    # 存档当前活跃订单的文件
    if current_active and current_active.id != new_order.id:  # 确保不是新创建的订单
        # 确保存档目录存在
        uploads_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'uploads', current_active.order_number)
        converted_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'converted', current_active.order_number)
        os.makedirs(uploads_archive, exist_ok=True)
        os.makedirs(converted_archive, exist_ok=True)
        
        logger.info(f"开始存档订单 #{current_active.order_number} 的文件")
        
        # 存档上传文件
        for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
            src_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(src_path):
                dst_path = os.path.join(uploads_archive, filename)
                try:
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"存档上传文件: {filename}")
                    
                    # 更新数据库中的文件路径记录
                    uploaded_file = UploadedFile.query.filter_by(
                        filename=filename, 
                        order_id=current_active.id
                    ).first()
                    if uploaded_file:
                        uploaded_file.file_path = dst_path
                except Exception as e:
                    logger.error(f"存档上传文件时出错 ({filename}): {str(e)}")
        
        # 存档转换文件
        for filename in os.listdir(current_app.config['CONVERTED_FOLDER']):
            src_path = os.path.join(current_app.config['CONVERTED_FOLDER'], filename)
            if os.path.isfile(src_path):
                dst_path = os.path.join(converted_archive, filename)
                try:
                    shutil.copy2(src_path, dst_path)
                    logger.info(f"存档转换文件: {filename}")
                    
                    # 更新数据库中的文件路径记录
                    converted_file = ConvertedFile.query.filter_by(
                        filename=filename, 
                        order_id=current_active.id
                    ).first()
                    if converted_file:
                        converted_file.file_path = dst_path
                except Exception as e:
                    logger.error(f"存档转换文件时出错 ({filename}): {str(e)}")
        
        # 不需要在这里设置，因为我们已经在上面将用户的所有订单设为非活跃了
        # current_active.is_active = False
    
    # 提交数据库更改
    db.session.commit()
    
    # 清空工作目录
    for folder in [current_app.config['UPLOAD_FOLDER'], current_app.config['CONVERTED_FOLDER']]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    
    flash(f'已创建新订单 #{new_order.order_number}')
    return redirect(url_for('main.index'))

@orders_bp.route('/activate/<order_number>', methods=['POST'])
@login_required
@csrf.exempt  # 豁免CSRF保护，因为可能通过AJAX调用
def activate_order(order_number):
    """激活（回滚到）指定订单"""
    # 检查是否是AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # 获取订单
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        logger.error(f"尝试激活不存在的订单: {order_number}")
        if is_ajax:
            return jsonify({'success': False, 'error': f'找不到订单 #{order_number}'})
        flash(f'找不到订单 #{order_number}')
        return redirect(url_for('orders.index'))
    
    # 检查权限
    current_user = AdminUser.query.get(session['admin_id'])
    if not current_user.is_admin and order.user_id != current_user.id:
        logger.warning(f"用户 {current_user.id} 无权激活订单 {order_number}")
        if is_ajax:
            return jsonify({'success': False, 'error': '您无权激活此订单'})
        flash('您无权激活此订单')
        return redirect(url_for('orders.index'))
    
    try:
        # 清空当前工作目录
        for folder in [current_app.config['UPLOAD_FOLDER'], current_app.config['CONVERTED_FOLDER']]:
            # 确保目录存在
            os.makedirs(folder, exist_ok=True)
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        
        # 修改活跃状态的逻辑，分为三种情况
        is_cross_user_operation = current_user.is_admin and order.user_id != current_user.id
        
        # 1. 管理员激活别人的订单（跨用户操作）
        if is_cross_user_operation:
            # 获取上次管理员激活的订单信息
            last_admin_activated_order_id = session.get('admin_activated_order')
            
            if last_admin_activated_order_id:
                # 取消上次管理员激活的订单的活跃状态
                last_order = Order.query.get(last_admin_activated_order_id)
                if last_order and last_order.is_active:
                    last_order.is_active = False
                    logger.info(f"管理员跨用户操作: 取消上次激活的订单 #{last_order.order_number} 的活跃状态")
            
            # 同时取消管理员自己的活跃订单
            admin_active_orders = Order.query.filter_by(
                user_id=current_user.id, 
                is_active=True
            ).all()
            
            for admin_order in admin_active_orders:
                admin_order.is_active = False
                logger.info(f"管理员跨用户操作: 取消管理员自己的活跃订单 #{admin_order.order_number}")
            
            # 将当前订单记录为管理员激活的订单
            session['admin_activated_order'] = order.id
            logger.info(f"管理员跨用户操作: 激活用户 {order.user_id} 的订单 #{order.order_number}")
        
        # 2. 管理员激活自己的订单
        elif current_user.is_admin and order.user_id == current_user.id:
            # 取消管理员之前激活的任何订单
            last_admin_activated_order_id = session.get('admin_activated_order')
            if last_admin_activated_order_id:
                last_order = Order.query.get(last_admin_activated_order_id)
                if last_order and last_order.is_active:
                    last_order.is_active = False
                    logger.info(f"管理员激活自己订单: 取消上次激活的订单 #{last_order.order_number} 的活跃状态")
            
            # 取消管理员自己其他的订单的活跃状态
            Order.query.filter(Order.user_id == current_user.id, Order.id != order.id).update({Order.is_active: False})
            
            # 清除管理员激活标记，因为现在是激活自己的订单
            session.pop('admin_activated_order', None)
            logger.info(f"管理员激活自己订单: 激活订单 #{order.order_number}")
        
        # 3. 普通用户激活自己的订单
        else:
            # 取消该用户其他所有订单的活跃状态
            Order.query.filter(Order.user_id == order.user_id, Order.id != order.id).update({Order.is_active: False})
            logger.info(f"普通用户操作: 取消用户 {order.user_id} 的其他订单活跃状态")
        
        # 将当前订单设为活跃
        order.is_active = True
        order.updated_at = datetime.now()
        db.session.commit()
        
        # 恢复订单文件
        # 获取订单中的上传文件记录
        uploaded_files = UploadedFile.query.filter_by(order_id=order.id).all()
        converted_files = ConvertedFile.query.filter_by(order_id=order.id).all()
        
        # 恢复文件到工作目录
        restored_uploads = 0
        restored_conversions = 0
        
        logger.info(f"尝试恢复上传文件: {len(uploaded_files)} 个文件记录")
        for file in uploaded_files:
            # 检查文件路径是否存在
            if file.file_path and os.path.exists(file.file_path):
                try:
                    # 从文件路径复制文件到工作目录
                    target_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
                    shutil.copy2(file.file_path, target_path)
                    logger.info(f"从路径恢复上传文件: {file.filename}, 源路径: {file.file_path}")
                    restored_uploads += 1
                except Exception as e:
                    logger.error(f"恢复上传文件时出错: {file.filename}, 源路径: {file.file_path}, 错误: {str(e)}")
            else:
                # 尝试从存档目录查找文件
                archive_path = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'uploads', order.order_number, file.filename)
                if os.path.exists(archive_path):
                    try:
                        target_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
                        shutil.copy2(archive_path, target_path)
                        logger.info(f"从存档恢复上传文件: {file.filename}, 源路径: {archive_path}")
                        restored_uploads += 1
                    except Exception as e:
                        logger.error(f"从存档恢复上传文件时出错: {file.filename}, 源路径: {archive_path}, 错误: {str(e)}")
                else:
                    logger.warning(f"无法恢复上传文件: {file.filename}, 文件路径不存在: {file.file_path}, 存档路径也不存在: {archive_path}")
        
        logger.info(f"尝试恢复转换文件: {len(converted_files)} 个文件记录")
        for file in converted_files:
            # 检查文件路径是否存在
            if file.file_path and os.path.exists(file.file_path):
                try:
                    # 从文件路径复制文件到工作目录
                    target_path = os.path.join(current_app.config['CONVERTED_FOLDER'], file.filename)
                    shutil.copy2(file.file_path, target_path)
                    logger.info(f"从路径恢复转换文件: {file.filename}, 源路径: {file.file_path}")
                    restored_conversions += 1
                except Exception as e:
                    logger.error(f"恢复转换文件时出错: {file.filename}, 源路径: {file.file_path}, 错误: {str(e)}")
            else:
                # 尝试从存档目录查找文件
                archive_path = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'converted', order.order_number, file.filename)
                if os.path.exists(archive_path):
                    try:
                        target_path = os.path.join(current_app.config['CONVERTED_FOLDER'], file.filename)
                        shutil.copy2(archive_path, target_path)
                        logger.info(f"从存档恢复转换文件: {file.filename}, 源路径: {archive_path}")
                        restored_conversions += 1
                    except Exception as e:
                        logger.error(f"从存档恢复转换文件时出错: {file.filename}, 源路径: {archive_path}, 错误: {str(e)}")
                else:
                    logger.warning(f"无法恢复转换文件: {file.filename}, 文件路径不存在: {file.file_path}, 存档路径也不存在: {archive_path}")
        
        # 恢复转换文件的特殊处理：如果是合并订单，尝试从原始订单获取文件
        if order.is_merged and order.merged_from:
            try:
                # 解析原始订单号列表
                source_order_numbers = order.merged_from.split(',')
                
                # 如果恢复的文件数量不足，尝试从原始订单获取
                if restored_conversions < len(converted_files):
                    logger.info(f"合并订单 #{order.order_number} 文件恢复不完整，尝试从原始订单获取")
                    
                    # 获取所有原始订单
                    source_orders = Order.query.filter(Order.order_number.in_(source_order_numbers)).all()
                    
                    # 从原始订单中查找缺失的转换文件
                    for source_order in source_orders:
                        source_converted_folder = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'converted', source_order.order_number)
                        
                        # 检查源订单的存档目录是否存在
                        if os.path.exists(source_converted_folder):
                            # 遍历当前订单中未恢复的转换文件
                            for file in converted_files:
                                # 检查该文件是否已恢复
                                target_path = os.path.join(current_app.config['CONVERTED_FOLDER'], file.filename)
                                if not os.path.exists(target_path):
                                    # 尝试从源订单的存档中查找
                                    source_path = os.path.join(source_converted_folder, file.filename)
                                    if os.path.exists(source_path):
                                        try:
                                            shutil.copy2(source_path, target_path)
                                            logger.info(f"从源订单 #{source_order.order_number} 恢复转换文件: {file.filename}")
                                            restored_conversions += 1
                                        except Exception as e:
                                            logger.error(f"从源订单恢复文件失败: {file.filename}, 错误: {str(e)}")
            except Exception as e:
                logger.error(f"从源订单恢复文件时出错: {str(e)}")
        
        logger.info(f"成功激活订单 #{order.order_number}，恢复了 {restored_uploads}/{len(uploaded_files)} 个上传文件和 {restored_conversions}/{len(converted_files)} 个转换文件")
        
        success_msg = f'成功回滚到订单 #{order.order_number}'
        if is_ajax:
            return jsonify({'success': True, 'message': success_msg})
        
        flash(success_msg)
    except Exception as e:
        logger.error(f"回滚订单时出错: {str(e)}")
        error_msg = f'回滚过程中发生错误: {str(e)}'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg)
    
    # 成功激活订单后重定向到订单的详情页面
    return redirect(url_for('orders.view_order', order_number=order.order_number))

@orders_bp.route('/update-status/<order_number>', methods=['POST'])
@login_required
@csrf.exempt  # 豁免CSRF保护，简化AJAX处理
def update_status(order_number):
    """更新订单状态"""
    # 检查是否是AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    logger.info(f"收到状态更新请求: order={order_number}, ajax={is_ajax}, form={request.form}")
    
    # 获取订单
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        error_msg = f'找不到订单 #{order_number}'
        logger.error(error_msg)
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg)
        return redirect(url_for('orders.index'))
    
    # 获取当前用户
    current_user = AdminUser.query.get(session['admin_id'])
    
    # 检查权限：只有管理员或订单创建者可以更改状态
    if not current_user.is_admin and order.user_id != current_user.id:
        error_msg = '您没有修改此订单状态的权限'
        logger.warning(f"用户 {current_user.id} 尝试修改无权访问的订单 {order_number}")
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(error_msg)
        return redirect(url_for('orders.index'))
    
    # 获取新状态
    new_status = request.form.get('status')
    logger.info(f"尝试将订单 {order_number} 状态从 {order.status} 更新为 {new_status}")
    
    if new_status not in [Order.STATUS_PENDING, Order.STATUS_MATERIAL, Order.STATUS_REVIEWED]:
        error_msg = f'无效的状态值: {new_status}'
        logger.error(error_msg)
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash('无效的状态值')
        return redirect(url_for('orders.view_order', order_number=order_number))
    
    # 记录旧状态以便在消息中显示变更
    old_status = order.status
    old_status_display = order.status_display
    
    # 更新状态
    order.status = new_status
    order.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        logger.info(f"成功更新订单 {order_number} 状态: {old_status} -> {new_status}")
        
        # 准备成功消息
        success_message = f'订单 #{order_number} 状态已从「{old_status_display}」更新为「{order.status_display}」'
        
        if is_ajax:
            return jsonify({
                'success': True, 
                'message': success_message,
                'new_status': order.status,
                'new_status_display': order.status_display
            })
        
        flash(success_message)
    except Exception as e:
        db.session.rollback()
        error_msg = f"更新订单状态时出错: {str(e)}"
        logger.error(error_msg)
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg})
        flash(f'更新状态失败: {str(e)}')
    
    # 根据请求源头决定返回的页面
    referrer = request.referrer
    if referrer and 'view' in referrer:
        # 如果是从详情页来的，返回详情页
        return redirect(url_for('orders.view_order', order_number=order_number))
    else:
        # 否则返回列表页
        return redirect(url_for('orders.index'))

@orders_bp.route('/view/<order_number>')
@login_required
def view_order(order_number):
    """查看订单详情"""
    # 获取订单
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        flash(f'找不到订单 #{order_number}')
        return redirect(url_for('orders.index'))
    
    # 检查权限：只有管理员或订单创建者可以查看
    current_user = AdminUser.query.get(session['admin_id'])
    if not current_user.is_admin and order.user_id != current_user.id:
        flash('您没有权限查看此订单')
        return redirect(url_for('orders.index'))
    
    # 获取转换文件列表
    converted_files = []
    
    # 只有当订单是活跃的且属于当前用户时，才显示工作目录中的文件
    if order.is_active and (order.user_id == current_user.id or current_user.is_admin):
        # 显示当前工作目录中的文件（确实属于当前用户）
        if os.path.exists(current_app.config['CONVERTED_FOLDER']):
            converted_files = os.listdir(current_app.config['CONVERTED_FOLDER'])
    else:
        # 如果是查看其他用户的订单或非活跃订单，从订单记录中获取文件信息
        # 这里只显示文件记录，而不是实际文件内容
        converted_files_records = ConvertedFile.query.filter_by(order_id=order.id).all()
        converted_files = [file.filename for file in converted_files_records]
    
    # 确定是否显示激活按钮
    can_activate = (current_user.id == order.user_id or current_user.is_admin) and not order.is_active
    
    # 确定是否显示工作目录中的文件
    is_active_order = order.is_active and (order.user_id == current_user.id or current_user.is_admin)
    
    # 如果是管理员，提供所有用户列表用于订单转交功能
    all_users = []
    if current_user.is_admin:
        all_users = AdminUser.query.all()
    
    return render_template('orders/view.html', 
                          order=order, 
                          converted_files=converted_files,
                          is_active_order=is_active_order,
                          can_activate=can_activate,
                          all_users=all_users,
                          current_user=current_user)

@orders_bp.route('/delete/<order_number>', methods=['POST'])
@login_required
def delete_order(order_number):
    """删除订单（需要管理员权限）"""
    # 这里应该检查用户是否有管理员权限
    current_user = AdminUser.query.get(session['admin_id'])
    if not current_user or not current_user.is_admin:
        flash('您没有删除订单的权限')
        return redirect(url_for('orders.index'))
    
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        flash(f'找不到订单 #{order_number}')
        return redirect(url_for('orders.index'))
    
    # 检查是否是用户的唯一活跃订单，如果是，则不允许删除
    if order.is_active and Order.query.filter_by(is_active=True, user_id=order.user_id).count() == 1:
        flash(f'不能删除用户的唯一活跃订单 #{order_number}，请先为该用户创建新订单')
        return redirect(url_for('orders.index'))
    
    # 在删除订单前，删除关联的物理文件
    try:
        # 先删除上传文件的物理文件
        for uploaded_file in order.files:
            if uploaded_file.file_path and os.path.exists(uploaded_file.file_path):
                try:
                    os.remove(uploaded_file.file_path)
                    logger.info(f"删除上传文件: {uploaded_file.file_path}")
                except Exception as e:
                    logger.error(f"删除上传文件失败: {uploaded_file.file_path}, 错误: {str(e)}")
        
        # 再删除转换文件的物理文件
        for converted_file in order.conversions:
            if converted_file.file_path and os.path.exists(converted_file.file_path):
                try:
                    os.remove(converted_file.file_path)
                    logger.info(f"删除转换文件: {converted_file.file_path}")
                except Exception as e:
                    logger.error(f"删除转换文件失败: {converted_file.file_path}, 错误: {str(e)}")
    except Exception as e:
        logger.error(f"删除订单文件时出错: {str(e)}")
    
    # 删除订单及关联数据
    db.session.delete(order)
    db.session.commit()
    
    flash(f'订单 #{order_number} 已删除')
    return redirect(url_for('orders.index'))

@orders_bp.route('/list')
@login_required
def list_orders():
    """获取订单列表（JSON API）"""
    # 获取当前用户
    current_user = AdminUser.query.get(session['admin_id'])
    
    # 根据用户权限获取不同的订单列表
    if current_user and current_user.is_admin:
        orders = Order.query.order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    # 转换为JSON格式
    orders_json = []
    for order in orders:
        order_data = order.to_dict()
        orders_json.append(order_data)
    
    return jsonify(orders_json)

@orders_bp.route('/update-note/<order_number>', methods=['POST'])
@login_required
@csrf.exempt  # 豁免CSRF保护，简化AJAX处理
def update_note(order_number):
    """更新订单备注"""
    # 检查是否是AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # 获取订单
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        if is_ajax:
            return jsonify({'success': False, 'error': f'找不到订单 #{order_number}'})
        flash(f'找不到订单 #{order_number}')
        return redirect(url_for('orders.index'))
    
    # 获取当前用户
    current_user = AdminUser.query.get(session['admin_id'])
    
    # 检查权限：只有管理员或订单创建者可以更改备注
    if not current_user.is_admin and order.user_id != current_user.id:
        if is_ajax:
            return jsonify({'success': False, 'error': '您没有修改此订单备注的权限'})
        flash('您没有修改此订单备注的权限')
        return redirect(url_for('orders.index'))
    
    try:
        # 获取新备注
        new_note = request.form.get('note', '').strip()
        old_note = order.note or '-'
        
        # 更新备注
        order.note = new_note
        order.updated_at = datetime.utcnow()
        db.session.commit()
        
        # 记录日志
        logger.info(f"更新订单 {order_number} 备注: {old_note} -> {new_note}")
        
        if is_ajax:
            return jsonify({
                'success': True, 
                'message': f'订单 #{order_number} 备注已更新',
                'new_note': new_note or '-'
            })
            
        flash(f'订单 #{order_number} 备注已更新')
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新订单备注时出错: {str(e)}")
        
        if is_ajax:
            return jsonify({'success': False, 'error': f'更新备注失败: {str(e)}'})
            
        flash(f'更新备注失败: {str(e)}')
    
    return redirect(url_for('orders.view_order', order_number=order_number))

@orders_bp.route('/merge-orders', methods=['POST'])
@login_required
@csrf.exempt  # 豁免CSRF保护，因为使用AJAX
def merge_orders():
    """合并多个订单为一个新订单"""
    # 获取当前用户
    current_user_id = session.get('admin_id')
    current_user = AdminUser.query.get(current_user_id)
    
    # 解析请求数据
    data = request.get_json()
    if not data or 'order_numbers' not in data:
        return jsonify({'success': False, 'error': '请求数据不完整'})
    
    order_numbers = data.get('order_numbers', [])
    note = data.get('note', '')
    
    # 验证订单数量
    if len(order_numbers) < 2:
        return jsonify({'success': False, 'error': '至少需要选择两个订单才能合并'})
    
    # 获取所有需要合并的订单
    orders_to_merge = Order.query.filter(Order.order_number.in_(order_numbers)).all()
    
    # 验证所有订单是否存在
    if len(orders_to_merge) != len(order_numbers):
        return jsonify({'success': False, 'error': '部分订单不存在'})
    
    # 验证权限：只能合并自己的订单，管理员可以合并所有订单
    if not current_user.is_admin:
        for order in orders_to_merge:
            if order.user_id != current_user_id:
                return jsonify({'success': False, 'error': '您没有权限合并其他用户的订单'})
    
    try:
        # 创建新订单
        merged_from = ','.join(order_numbers)
        display_note = note or f"由订单 {', '.join(order_numbers)} 合并而来"
        
        new_order = Order(
            order_number=Order.generate_order_number(),
            is_active=False,  # 默认不设为活跃
            status=Order.STATUS_PENDING,
            user_id=current_user_id,
            note=display_note,
            is_merged=True,
            merged_from=merged_from
        )
        db.session.add(new_order)
        db.session.flush()  # 获取new_order.id
        
        # 确保新订单的存档目录存在
        new_uploads_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'uploads', new_order.order_number)
        new_converted_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'converted', new_order.order_number)
        os.makedirs(new_uploads_archive, exist_ok=True)
        os.makedirs(new_converted_archive, exist_ok=True)
        
        # 记录已处理的文件，避免重复
        processed_files = set()
        
        # 为每个原始订单复制文件到新订单
        for order in orders_to_merge:
            # 复制上传文件
            for uploaded_file in order.files:
                # 检查文件是否已存在(根据文件哈希或文件名)
                file_identifier = uploaded_file.file_hash or uploaded_file.filename
                if file_identifier in processed_files:
                    continue
                
                # 复制实际文件到新订单的存档目录
                new_file_path = os.path.join(new_uploads_archive, uploaded_file.filename)
                file_copied = False
                
                # 尝试从原始文件路径复制
                if uploaded_file.file_path and os.path.exists(uploaded_file.file_path):
                    try:
                        shutil.copy2(uploaded_file.file_path, new_file_path)
                        file_copied = True
                        logger.info(f"已复制上传文件 {uploaded_file.filename} 到合并订单 #{new_order.order_number}")
                    except Exception as e:
                        logger.error(f"复制上传文件到合并订单失败: {uploaded_file.filename}, 错误: {str(e)}")
                
                # 如果文件路径不存在，尝试从工作目录
                if not file_copied:
                    work_path = os.path.join(current_app.config['UPLOAD_FOLDER'], uploaded_file.filename)
                    if os.path.exists(work_path):
                        try:
                            shutil.copy2(work_path, new_file_path)
                            file_copied = True
                            logger.info(f"已从工作目录复制上传文件 {uploaded_file.filename} 到合并订单 #{new_order.order_number}")
                        except Exception as e:
                            logger.error(f"从工作目录复制上传文件失败: {uploaded_file.filename}, 错误: {str(e)}")
                
                # 如果仍未复制成功，尝试从原订单存档目录
                if not file_copied:
                    order_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'uploads', order.order_number, uploaded_file.filename)
                    if os.path.exists(order_archive):
                        try:
                            shutil.copy2(order_archive, new_file_path)
                            file_copied = True
                            logger.info(f"已从原订单存档复制上传文件 {uploaded_file.filename} 到合并订单 #{new_order.order_number}")
                        except Exception as e:
                            logger.error(f"从原订单存档复制上传文件失败: {uploaded_file.filename}, 错误: {str(e)}")
                
                # 创建新的上传文件记录，使用新的文件路径
                new_uploaded_file = UploadedFile(
                    filename=uploaded_file.filename,
                    original_filename=uploaded_file.original_filename,
                    file_path=new_file_path if file_copied else uploaded_file.file_path,  # 使用新路径或保留旧路径
                    file_size=uploaded_file.file_size,
                    file_type=uploaded_file.file_type,
                    file_hash=uploaded_file.file_hash,
                    order_id=new_order.id
                )
                db.session.add(new_uploaded_file)
                processed_files.add(file_identifier)
                
                # 复制相关的转换文件
                for converted_file in uploaded_file.conversions:
                    # 复制实际文件到新订单的转换存档目录
                    new_conv_path = os.path.join(new_converted_archive, converted_file.filename)
                    conv_copied = False
                    
                    # 尝试从原始文件路径复制
                    if converted_file.file_path and os.path.exists(converted_file.file_path):
                        try:
                            shutil.copy2(converted_file.file_path, new_conv_path)
                            conv_copied = True
                            logger.info(f"已复制转换文件 {converted_file.filename} 到合并订单 #{new_order.order_number}")
                        except Exception as e:
                            logger.error(f"复制转换文件到合并订单失败: {converted_file.filename}, 错误: {str(e)}")
                    
                    # 如果文件路径不存在，尝试从转换文件夹
                    if not conv_copied:
                        work_path = os.path.join(current_app.config['CONVERTED_FOLDER'], converted_file.filename)
                        if os.path.exists(work_path):
                            try:
                                shutil.copy2(work_path, new_conv_path)
                                conv_copied = True
                                logger.info(f"已从工作目录复制转换文件 {converted_file.filename} 到合并订单 #{new_order.order_number}")
                            except Exception as e:
                                logger.error(f"从工作目录复制转换文件失败: {converted_file.filename}, 错误: {str(e)}")
                    
                    # 如果仍未复制成功，尝试从原订单转换存档目录
                    if not conv_copied:
                        order_conv_archive = os.path.join(current_app.config['ARCHIVE_FOLDER'], 'converted', order.order_number, converted_file.filename)
                        if os.path.exists(order_conv_archive):
                            try:
                                shutil.copy2(order_conv_archive, new_conv_path)
                                conv_copied = True
                                logger.info(f"已从原订单存档复制转换文件 {converted_file.filename} 到合并订单 #{new_order.order_number}")
                            except Exception as e:
                                logger.error(f"从原订单存档复制转换文件失败: {converted_file.filename}, 错误: {str(e)}")
                    
                    # 创建新的转换文件记录
                    new_converted_file = ConvertedFile(
                        filename=converted_file.filename,
                        file_path=new_conv_path if conv_copied else converted_file.file_path,  # 使用新路径或保留旧路径
                        source_file_id=new_uploaded_file.id,  # 关联到新的上传文件
                        source_hash=converted_file.source_hash,
                        from_zip=converted_file.from_zip,
                        zip_path=new_file_path if file_copied and converted_file.from_zip else converted_file.zip_path,  # 更新ZIP路径
                        order_id=new_order.id
                    )
                    db.session.add(new_converted_file)
        
        # 提交数据库更改
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'已成功创建合并订单 #{new_order.order_number}，包含 {len(processed_files)} 个文件',
            'order_number': new_order.order_number
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"合并订单时出错: {str(e)}")
        return jsonify({'success': False, 'error': f'合并订单时出错: {str(e)}'}) 

@orders_bp.route('/transfer/<order_number>', methods=['POST'])
@login_required
@csrf.exempt  # 豁免CSRF保护，因为使用AJAX
def transfer_order(order_number):
    """转交订单给其他用户（仅管理员可用）"""
    # 获取当前用户
    current_user_id = session.get('admin_id')
    current_user = AdminUser.query.get(current_user_id)
    
    # 验证权限：仅管理员可以转交订单
    if not current_user or not current_user.is_admin:
        return jsonify({'success': False, 'error': '只有管理员可以转交订单'})
    
    # 获取参数
    target_user_id = request.form.get('target_user_id')
    note = request.form.get('note', '')
    
    if not target_user_id:
        return jsonify({'success': False, 'error': '请选择目标用户'})
    
    try:
        # 查找订单和目标用户
        order = Order.query.filter_by(order_number=order_number).first()
        target_user = AdminUser.query.get(target_user_id)
        
        if not order:
            return jsonify({'success': False, 'error': f'找不到订单 #{order_number}'})
        if not target_user:
            return jsonify({'success': False, 'error': '找不到目标用户'})
        
        # 记录转交前的信息用于日志
        previous_user_id = order.user_id
        previous_user = AdminUser.query.get(previous_user_id)
        previous_username = previous_user.username if previous_user else "未知用户"
        
        # 如果订单当前是活跃状态，需要先取消活跃状态
        if order.is_active:
            order.is_active = False
            
        # 更新订单所有者
        order.user_id = target_user_id
        
        # 添加转交备注（可选）
        if note:
            transfer_note = f"[系统备注：订单由 {previous_username} 转交给 {target_user.username}]"
            if note:
                transfer_note += f"[转交备注: {note}]"
                
            # 如果原有备注存在则保留
            if order.note:
                order.note = f"{order.note} {transfer_note}"
            else:
                order.note = transfer_note
            
        # 记录最后更新时间
        order.updated_at = datetime.now()
        
        # 提交更改
        db.session.commit()
        
        # 记录日志
        logger.info(f"订单 #{order.order_number} 已从用户 {previous_username} 转交给用户 {target_user.username}")
        
        return jsonify({
            'success': True, 
            'message': f'订单已成功转交给用户 {target_user.username}'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"转交订单时出错: {str(e)}")
        return jsonify({'success': False, 'error': f'转交订单时出错: {str(e)}'}) 