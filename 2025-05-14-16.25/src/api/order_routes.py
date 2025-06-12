from flask import render_template, redirect, url_for, request, flash, jsonify
from functools import wraps
import os

from src.api import orders_bp
from src.services.admin_service import AdminService
from src.services.order_service import OrderService

# 登录装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not AdminService.is_authenticated():
            flash('请先登录', 'error')
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@orders_bp.route('/')
@login_required
def index():
    """订单首页，与order_list功能相同"""
    return order_list()

@orders_bp.route('/list')
@login_required
def order_list():
    """订单列表"""
    orders = OrderService.get_all_orders()
    return render_template('orders/index.html', orders=orders)

@orders_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete_orders():
    """批量删除订单"""
    # 检查是否是JSON请求
    if request.is_json:
        # 处理JSON格式请求
        data = request.json
        order_ids = data.get('order_ids', [])
        order_numbers = data.get('order_numbers', [])
        
        # 如果提供了order_numbers而不是order_ids，则查找对应的order_ids
        if not order_ids and order_numbers:
            order_ids = []
            for order_number in order_numbers:
                order = OrderService.get_order_by_number(order_number)
                if order:
                    order_ids.append(order.id)
    else:
        # 处理表单格式请求
        # 对于单个订单删除，使用表单中的order_ids参数
        order_ids_str = request.form.get('order_ids', '')
        if order_ids_str:
            try:
                # 转换为整数列表
                order_ids = [int(order_ids_str)]
            except ValueError:
                order_ids = []
        else:
            # 对于批量删除，使用order_ids[]参数
            order_ids = request.form.getlist('order_ids[]')
            order_ids = [int(oid) for oid in order_ids if oid.isdigit()]
    
    if not order_ids:
        if request.is_json:
            return jsonify(success=False, message='未选择订单')
        flash('未选择订单', 'error')
        return redirect(url_for('orders.index'))
    
    # 批量删除订单
    success = OrderService.delete_orders(order_ids)
    
    if request.is_json:
        if success:
            return jsonify(success=True, message='订单删除成功')
        else:
            return jsonify(success=False, message='部分或全部订单删除失败')
    
    if success:
        flash('订单删除成功', 'success')
    else:
        flash('部分或全部订单删除失败', 'error')
    
    # 重定向回订单列表页面
    return redirect(url_for('orders.index'))

@orders_bp.route('/create', methods=['POST'])
@login_required
def create_order():
    """创建新订单"""
    order = OrderService.create_order()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, order=order.to_dict())
    
    flash(f'订单 {order.order_number} 创建成功', 'success')
    return redirect(url_for('orders.order_detail', order_number=order.order_number))

@orders_bp.route('/<order_number>')
@login_required
def order_detail(order_number):
    """订单详情"""
    # 尝试通过订单号获取订单
    order = OrderService.get_order_by_number(order_number)
    
    # 兼容旧URL格式（如果order_number是数字ID）
    if not order and order_number.isdigit():
        order = OrderService.get_order(int(order_number))
    
    if not order:
        flash('订单不存在', 'error')
        return redirect(url_for('orders.order_list'))
    
    # 获取订单的所有文件
    uploaded_files = OrderService.get_order_files(order.id)
    
    # 获取订单的转换后文件并确保只包含属于当前订单的文件
    converted_files_objs = OrderService.get_order_conversions(order.id)
    
    # 将ConvertedFile对象列表转换为文件名列表
    converted_files = []
    if converted_files_objs:
        for cf in converted_files_objs:
            # 确保文件属于当前订单
            if cf.order_id == order.id:
                # 取文件名而不是整个路径
                filename = os.path.basename(cf.file_path)
                converted_files.append(filename)
        
        # 按文件名排序
        converted_files.sort(key=lambda x: (
            # 首先按前缀排序（01_申请表、02_证件照等）
            x.split('_')[0] if '_' in x and x.split('_')[0].isdigit() else '99',
            # 然后按类别排序
            x.split('_')[1] if '_' in x and len(x.split('_')) > 1 else '',
            # 最后按序号排序
            int(x.split('_')[2].split('.')[0]) if '_' in x and len(x.split('_')) > 2 and 
            x.split('_')[2].split('.')[0].isdigit() else 9999
        ))
    
    # 添加筛选参数
    filter_params = {}
    for key in request.args:
        if key not in ['page', 'per_page']:
            filter_params[key] = request.args.get(key)
    
    # 获取当前用户
    current_user = AdminService.get_current_user()
    
    return render_template('orders/view.html', 
                           order=order,
                           uploaded_files=uploaded_files,
                           converted_files=converted_files,
                           filter_params=filter_params,
                           current_user=current_user)

@orders_bp.route('/<order_number>/status', methods=['POST'])
@login_required
def update_order_status(order_number):
    """更新订单状态"""
    # 尝试通过订单号获取订单
    order = OrderService.get_order_by_number(order_number)
    
    # 兼容旧URL格式（如果order_number是数字ID）
    if not order and order_number.isdigit():
        order = OrderService.get_order(int(order_number))
    
    if not order:
        flash('订单不存在', 'error')
        return redirect(url_for('orders.order_list'))
    
    new_status = request.form.get('status')
    if not new_status:
        flash('未提供状态', 'error')
        return redirect(url_for('orders.order_detail', order_number=order.order_number))
    
    updated_order = OrderService.update_order_status(order.id, new_status)
    
    if updated_order:
        flash('订单状态已更新', 'success')
    else:
        flash('操作失败', 'error')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=bool(updated_order))
    
    return redirect(url_for('orders.order_detail', order_number=order.order_number))

@orders_bp.route('/merge', methods=['POST'])
@login_required
def merge_orders():
    """合并多个订单"""
    order_ids = request.form.getlist('order_ids[]')
    if not order_ids:
        flash('请选择要合并的订单', 'error')
        return redirect(url_for('orders.order_list'))
    
    # 转换为整数列表
    order_ids = [int(oid) for oid in order_ids]
    
    # 合并订单
    new_order = OrderService.merge_orders(order_ids)
    
    if new_order:
        flash(f'已成功合并为新订单: {new_order.order_number}', 'success')
        return redirect(url_for('orders.order_detail', order_number=new_order.order_number))
    else:
        flash('订单合并失败', 'error')
        return redirect(url_for('orders.order_list'))

@orders_bp.route('/<order_number>/note', methods=['POST'])
@login_required
def update_note(order_number):
    """更新订单备注"""
    # 尝试通过订单号获取订单
    order = OrderService.get_order_by_number(order_number)
    
    # 兼容旧URL格式（如果order_number是数字ID）
    if not order and order_number.isdigit():
        order = OrderService.get_order(int(order_number))
    
    if not order:
        flash('订单不存在', 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(success=False, message='订单不存在')
        return redirect(url_for('orders.order_list'))
    
    note = request.form.get('note', '')
    
    success = OrderService.update_order_note(order.id, note)
    
    if success:
        flash('订单备注已更新', 'success')
    else:
        flash('更新订单备注失败', 'error')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=success)
    
    return redirect(url_for('orders.order_detail', order_number=order.order_number))
