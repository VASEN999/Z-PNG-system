from flask import render_template, redirect, url_for, request, flash, session
from functools import wraps
import datetime
from urllib.parse import urlparse

from src.api import admin_bp, csrf
from src.services.admin_service import AdminService
from src.services.order_service import OrderService

# 管理员装饰器
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AdminService.is_authenticated():
            flash('请先登录', 'error')
            return redirect(url_for('admin.login'))
        
        if not AdminService.is_admin():
            flash('权限不足', 'error')
            return redirect(url_for('main.index'))
            
        return f(*args, **kwargs)
    return decorated_function

# 登录装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AdminService.is_authenticated():
            flash('请先登录', 'error')
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    """管理员首页，与dashboard功能相同"""
    return dashboard()

@admin_bp.route('/login', methods=['GET', 'POST'])
@csrf.exempt  # 豁免CSRF保护
def login():
    """用户登录"""
    # 如果已经登录，直接跳转到首页
    if AdminService.is_authenticated():
        # 检查是否是管理员
        if AdminService.is_admin():
            return redirect(url_for('admin.dashboard'))  # 管理员跳转到管理面板
        else:
            return redirect(url_for('main.index'))   # 普通用户跳转到首页
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return redirect(url_for('admin.login'))
        
        # 验证用户
        user = AdminService.authenticate(username, password)
        
        if user:
            # 处理重定向
            next_page = request.form.get('next') or request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                if user.is_admin:
                    next_page = url_for('admin.dashboard')  # 管理员跳转到管理面板
                else:
                    next_page = url_for('orders.order_list')   # 普通用户跳转到订单列表
            
            flash('登录成功！', 'success')
            return redirect(next_page)
        else:
            flash('用户名或密码不正确', 'error')
    
    # 显示登录表单
    return render_template('admin/login.html')

@admin_bp.route('/logout')
def logout():
    """用户登出"""
    AdminService.logout()
    flash('已成功登出', 'success')
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """管理员仪表盘"""
    users = AdminService.get_all_users()
    return render_template('admin/dashboard.html', users=users)

@admin_bp.route('/users')
@admin_required
def users():
    """用户管理，与user_list功能相同"""
    return user_list()

@admin_bp.route('/users-list')
@admin_required
def user_list():
    """用户列表"""
    users = AdminService.get_all_users()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/orders')
@admin_required
def orders():
    """订单管理页面"""
    orders = OrderService.get_all_orders()
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/settings')
@admin_required
def settings():
    """系统设置页面"""
    # 添加当前时间变量供模板使用
    now = datetime.datetime.now()
    return render_template('admin/settings.html', now=now)

@admin_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """修改密码页面"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_password or not new_password or not confirm_password:
            flash('请填写所有密码字段', 'error')
            return redirect(url_for('admin.change_password'))
        
        if new_password != confirm_password:
            flash('新密码和确认密码不匹配', 'error')
            return redirect(url_for('admin.change_password'))
        
        # 验证当前密码并更新
        success = AdminService.update_password(current_password, new_password)
        
        if success:
            flash('密码修改成功', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('当前密码不正确', 'error')
            return redirect(url_for('admin.change_password'))
    
    return render_template('admin/change_password.html')

@admin_bp.route('/add-user', methods=['GET', 'POST'])
@admin_required
def add_user():
    """添加用户的别名路由，指向create_user函数"""
    return create_user()

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@admin_required
def create_user():
    """创建用户"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        is_admin = request.form.get('is_admin') == 'on'
        
        # 通过服务层创建用户
        user = AdminService.create_user(username, password, is_admin, email, full_name)
        
        if user:
            flash('用户创建成功', 'success')
            return redirect(url_for('admin.user_list'))
        else:
            flash('用户创建失败，用户名可能已存在', 'error')
    
    return render_template('admin/create_user.html')

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """编辑用户"""
    user = AdminService.get_user(user_id)
    if not user:
        flash('用户不存在', 'error')
        return redirect(url_for('admin.user_list'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        is_admin = request.form.get('is_admin') == 'on'
        
        # 如果提供了新密码，则更新密码
        new_password = request.form.get('new_password')
        if new_password:
            AdminService.update_user(user_id, password=new_password)
        
        # 更新其他信息
        updated_user = AdminService.update_user(
            user_id,
            email=email,
            full_name=full_name,
            is_admin=is_admin
        )
        
        if updated_user:
            flash('用户信息更新成功', 'success')
            return redirect(url_for('admin.user_list'))
        else:
            flash('用户信息更新失败', 'error')
    
    return render_template('admin/edit_user.html', user=user)
