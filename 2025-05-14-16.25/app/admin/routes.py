import os
import logging
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse
from flask import render_template, request, redirect, url_for, flash, session, jsonify, current_app
from flask_wtf.csrf import CSRFProtect

from . import admin_bp
from models import db, AdminUser, Order
from app import csrf  # 导入从app/__init__.py创建的csrf对象

# 获取日志记录器
logger = logging.getLogger(__name__)

# 管理员登录装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('请先登录管理员账号')
            return redirect(url_for('admin.login', next=request.url))
        
        # 检查是否是管理员
        user = AdminUser.query.get(session['admin_id'])
        if not user or not user.is_admin:
            flash('您没有管理员权限')
            return redirect(url_for('main.index'))
            
        return f(*args, **kwargs)
    return decorated_function

# 用户登录装饰器(允许管理员和普通用户)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('请先登录')
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    """管理员控制面板首页"""
    # 获取统计数据
    orders_count = Order.query.count()
    active_orders = Order.query.filter_by(is_active=True).count()
    
    # 获取最近的订单
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    
    return render_template('admin/index.html', 
                          orders_count=orders_count,
                          active_orders=active_orders,
                          recent_orders=recent_orders)

# 为登录路由临时豁免CSRF保护，方便调试
@admin_bp.route('/login', methods=['GET', 'POST'])
@csrf.exempt  # 添加CSRF豁免
def login():
    """用户登录"""
    try:
        logger.info(f"登录尝试开始 - 方法: {request.method}, 来源: {request.remote_addr}")
        logger.info(f"请求参数: {request.args}")
        logger.info(f"表单数据: {request.form}")
        
        # 如果已经登录，直接跳转到首页
        if 'admin_id' in session:
            logger.info(f"用户已登录，session: {session}")
            # 检查是否是管理员
            user = AdminUser.query.get(session['admin_id'])
            if user and user.is_admin:
                return redirect(url_for('admin.index'))  # 管理员跳转到管理面板
            else:
                return redirect(url_for('main.index'))   # 普通用户跳转到首页
        
        if request.method == 'POST':
            logger.info("处理POST请求")
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not username or not password:
                logger.warning("用户名或密码为空")
                flash('请输入用户名和密码')
                return redirect(url_for('admin.login'))
            
            # 查询用户
            user = AdminUser.query.filter_by(username=username).first()
            
            # 验证用户和密码
            if user and user.check_password(password):
                # 检查用户是否被禁用
                if not user.is_active:
                    logger.warning(f"用户 {username} 已被禁用")
                    flash('账户已被禁用，请联系管理员')
                    return redirect(url_for('admin.login'))
                    
                logger.info(f"用户 {username} 验证成功")
                # 将用户ID和用户名添加到会话
                session['admin_id'] = user.id
                session['admin_username'] = user.username
                session.permanent = True  # 使session持久化
            
                # 更新最后登录时间
                user.last_login = datetime.now()
                
                # 清空工作目录中的文件，为新登录的用户提供干净的工作环境
                try:
                    # 清空上传文件夹
                    for filename in os.listdir(current_app.config['UPLOAD_FOLDER']):
                        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    
                    # 清空转换文件夹
                    for filename in os.listdir(current_app.config['CONVERTED_FOLDER']):
                        file_path = os.path.join(current_app.config['CONVERTED_FOLDER'], filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    
                    # 将当前用户的所有活跃订单标记为非活跃
                    Order.query.filter_by(is_active=True, user_id=user.id).update({Order.is_active: False})
                    
                    # 查找用户最近的订单并设为活跃(如果存在)
                    latest_order = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).first()
                    if latest_order:
                        latest_order.is_active = True
                        logger.info(f"为用户 {username} 激活最近的订单 #{latest_order.order_number}")
                    # 不再自动创建新订单
                    
                    db.session.commit()
                except Exception as e:
                    logger.error(f"清理工作目录时出错: {str(e)}")
                
                # 处理重定向
                next_page = request.form.get('next') or request.args.get('next')
                if not next_page or urlparse(next_page).netloc != '':
                    if user.is_admin:
                        next_page = url_for('admin.index')  # 管理员跳转到管理面板
                    else:
                        next_page = url_for('orders.index')   # 普通用户跳转到订单列表页面
                
                logger.info(f"重定向到: {next_page}")
                return redirect(next_page)
            else:
                logger.warning(f"用户 {username} 验证失败")
                flash('用户名或密码不正确')
        
        # 显示登录表单
        return render_template('admin/login.html')
    except Exception as e:
        logger.error(f"登录发生错误: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'登录时出错: {str(e)}')
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>登录错误</title></head>
        <body>
            <h1>登录出错</h1>
            <p>{str(e)}</p>
            <pre>{traceback.format_exc()}</pre>
            <p><a href="/admin/login">返回登录页面</a></p>
        </body>
        </html>
        """

@admin_bp.route('/logout')
def logout():
    """管理员登出"""
    # 获取当前用户ID，用于后续处理其活跃订单
    current_user_id = session.get('admin_id')
    
    if current_user_id:
        try:
            # 将该用户的所有活跃订单设为非活跃
            Order.query.filter_by(is_active=True, user_id=current_user_id).update({Order.is_active: False})
            db.session.commit()
            logger.info(f"用户 ID:{current_user_id} 登出，已将其所有活跃订单设为非活跃")
        except Exception as e:
            logger.error(f"用户登出时更新订单状态出错: {str(e)}")
            db.session.rollback()
    
    # 清除会话
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('已成功登出')
    return redirect(url_for('admin.login'))

@admin_bp.route('/change_password', methods=['GET', 'POST'])
@admin_required
def change_password():
    """修改管理员密码"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([current_password, new_password, confirm_password]):
            flash('所有字段都必须填写')
            return render_template('admin/change_password.html')
        
        if new_password != confirm_password:
            flash('新密码两次输入不一致')
            return render_template('admin/change_password.html')
        
        admin = AdminUser.query.get(session['admin_id'])
        if not admin.check_password(current_password):
            flash('当前密码不正确')
            return render_template('admin/change_password.html')
        
        # 更新密码
        admin.set_password(new_password)
        db.session.commit()
        
        flash('密码已成功更新')
        return redirect(url_for('admin.index'))
    
    return render_template('admin/change_password.html')

@admin_bp.route('/orders')
@admin_required
def orders():
    """订单管理界面"""
    try:
        logger.info("进入管理员订单页面")
        
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
        
        # 获取订单列表
        orders = query.order_by(Order.created_at.desc()).all()
        
        # 获取所有用户列表（用于创建人筛选下拉框）
        users = AdminUser.query.all()
        
        # 如果筛选了创建人，获取创建人名称用于显示在筛选标签中
        creator_name = None
        if creator_filter:
            creator = AdminUser.query.get(int(creator_filter))
            if creator:
                creator_name = creator.username
        
        logger.info(f"成功获取订单列表，共 {len(orders)} 条记录")
        
        # 返回模板
        return render_template('admin/orders.html', 
                               orders=orders, 
                               users=users,
                               creator_name=creator_name)
    except Exception as e:
        logger.error(f"管理员订单页面出错：{str(e)}")
        # 打印详细的错误堆栈
        import traceback
        logger.error(traceback.format_exc())
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>错误</title></head>
        <body>
            <h1>出错了</h1>
            <p>{str(e)}</p>
            <pre>{traceback.format_exc()}</pre>
        </body>
        </html>
        """

@admin_bp.route('/settings')
@admin_required
def settings():
    """系统设置界面"""
    return render_template('admin/settings.html')

@admin_bp.route('/api/delete_order/<order_number>', methods=['POST'])
@admin_required
@csrf.exempt  # 豁免CSRF保护
def api_delete_order(order_number):
    """API：删除订单"""
    try:
        order = Order.query.filter_by(order_number=order_number).first()
        if not order:
            return jsonify({
                'success': False,
                'message': f'找不到订单 #{order_number}'
            })
        
        # 如果是唯一的活跃订单，则不允许删除
        if order.is_active and Order.query.filter_by(is_active=True).count() == 1:
            return jsonify({
                'success': False,
                'message': f'不能删除唯一的活跃订单 #{order_number}，请先创建新订单'
            })
        
        # 删除订单及其关联的文件
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'订单 #{order_number} 已成功删除'
        })
    except Exception as e:
        logger.error(f"删除订单时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除订单时出错: {str(e)}'
        })

@admin_bp.route('/users')
@admin_required
def users():
    """用户管理界面"""
    users = AdminUser.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    """添加新用户"""
    if request.method == 'POST':
        # 获取表单数据
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        
        # 修复角色选择逻辑，根据radio按钮的值决定是否是管理员
        is_admin = request.form.get('is_admin') == 'yes'
        
        # 活跃状态默认为True
        is_active = 'is_active' in request.form if 'is_active' in request.form else True
        
        # 验证数据
        if not username or not password:
            flash('用户名和密码是必填项')
            return render_template('admin/add_user.html')
        
        # 检查用户名是否已存在
        if AdminUser.query.filter_by(username=username).first():
            flash('用户名已存在，请使用其他用户名')
            return render_template('admin/add_user.html')
        
        # 创建新用户
        try:
            new_user = AdminUser(
                username=username,
                full_name=full_name,
                email=email,
                is_admin=is_admin,
                is_active=is_active
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'用户 {username} 创建成功')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建用户时出错: {str(e)}')
            return render_template('admin/add_user.html')
    
    return render_template('admin/add_user.html')

@admin_bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """编辑用户信息"""
    user = AdminUser.query.get_or_404(user_id)
    
    # 判断是否在编辑自己的账户
    admin_self = user.id == session.get('admin_id')
    
    # 不允许编辑自己的管理员权限
    if admin_self and request.method == 'POST' and request.form.get('is_admin') != 'yes':
        flash('不能移除自己的管理员权限')
        return redirect(url_for('admin.users'))
    
    if request.method == 'POST':
        # 获取表单数据
        user.full_name = request.form.get('full_name', '')
        user.email = request.form.get('email', '')
        
        # 只有不是自己才能修改这些权限
        if not admin_self:
            user.is_admin = request.form.get('is_admin') == 'yes'
            user.is_active = request.form.get('is_active') == 'yes'
        
        new_password = request.form.get('password')
        if new_password:  # 如果提供了新密码
            user.set_password(new_password)
        
        try:
            db.session.commit()
            flash(f'用户 {user.username} 更新成功')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新用户时出错: {str(e)}')
    
    return render_template('admin/edit_user.html', user=user, admin_self=admin_self)

@admin_bp.route('/api/delete_user/<int:user_id>', methods=['POST'])
@admin_required
@csrf.exempt
def api_delete_user(user_id):
    """API: 删除用户"""
    # 不能删除自己
    if user_id == session.get('admin_id'):
        return jsonify({
            'success': False,
            'message': '不能删除自己的账户'
        })
    
    try:
        user = AdminUser.query.get(user_id)
        if not user:
            return jsonify({
                'success': False,
                'message': '找不到指定用户'
            })
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'用户 {username} 已成功删除'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除用户时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除用户时出错: {str(e)}'
        }) 