from flask import Blueprint, render_template, redirect, url_for, request, session, flash, send_from_directory, jsonify, abort, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from functools import wraps
import json
import zipfile
from flask import after_this_request
import shutil
import requests
import urllib.parse
import threading

from src.api import main_bp
from src.services.admin_service import AdminService
from src.services.file_service import FileService
from src.services.order_service import OrderService
from src.utils.decorators import login_required
from src.repositories.file_repo import FileRepository
from src.models import db  # 导入数据库会话

# 主页路由
@main_bp.route('/')
def index():
    """主页"""
    # 获取当前用户的活跃订单
    active_order = None
    if AdminService.is_authenticated():
        user_id = session.get('admin_id')
        active_order = OrderService.get_active_order(user_id)
    
    return render_template('index.html', active_order=active_order)

# 文件上传路由
@main_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_file():
    """文件上传页面"""
    if request.method == 'POST':
        # 检查是否有文件上传
        has_files = False
        uploaded_files = []
        
        # 检查单文件上传（兼容旧表单）
        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                has_files = True
                uploaded_files.append(file)
        
        # 检查多文件上传
        if 'files[]' in request.files:
            files = request.files.getlist('files[]')
            for file in files:
                if file.filename != '':
                    has_files = True
                    uploaded_files.append(file)
        
        # 如果没有文件被选择
        if not has_files:
            flash('没有选择文件', 'error')
            return redirect(request.url)
        
        # 优先使用表单中传递的order_id，如果没有则创建新订单
        order = None
        order_id = request.form.get('order_id')
        
        if order_id:
            order = OrderService.get_order(int(order_id))
        
        # 如果没有找到指定订单，创建新订单
        if not order:
            order = OrderService.create_order()
            flash(f'已创建新订单: {order.order_number}', 'info')
        
        # 保存所有上传的文件
        success_count = 0
        for file in uploaded_files:
            uploaded_file = FileService.save_uploaded_file(file, order.id)
            if uploaded_file:
                success_count += 1
        
        # 提示消息
        if success_count > 0:
            if success_count == 1:
                flash(f'文件上传成功', 'success')
            else:
                flash(f'{success_count}个文件上传成功', 'success')
            
            # 跳转到订单详情页而不是文件列表
            return redirect(url_for('orders.order_detail', order_number=order.order_number))
        else:
            flash('文件上传失败', 'error')
    
    return render_template('upload.html')

# 处理文件路由
@main_bp.route('/process', methods=['POST'])
@login_required
def process():
    """处理已上传的文件"""
    try:
        # 获取指定的订单ID
        order_id = request.form.get('order_id')
        current_order = None
        
        if order_id:
            current_order = OrderService.get_order(int(order_id))
        
        if not current_order:
            flash('请指定要处理文件的订单', 'error')
            return redirect(url_for('orders.index'))
        
        # 获取所有已选中的文件ID
        selected_file_ids = request.form.getlist('selected_files[]')
        
        # 如果没有提交selected_files[]，获取当前订单中的所有文件
        if not selected_file_ids:
            # 获取当前订单中的所有文件
            files = OrderService.get_order_files(current_order.id)
            
            if not files:
                flash('当前订单没有可处理的文件，请先上传文件')
                return redirect(url_for('orders.order_detail', order_number=current_order.order_number))
            
            selected_file_ids = [str(f.id) for f in files]
        
        # 处理每个选中的文件
        processed_count = 0
        for file_id in selected_file_ids:
            # 通过服务层获取文件
            file = FileService.get_uploaded_file(int(file_id))
            
            # 确保文件存在且属于当前订单
            if not file or file.order_id != current_order.id:
                continue
                
            # 检查文件类型并进行相应处理
            if file.file_path.lower().endswith('.pdf'):
                # 调用服务层进行PDF转换
                FileService.convert_pdf(file)
                processed_count += 1
            elif file.file_path.lower().endswith(('.docx', '.doc')):
                # 调用服务层进行Word文档转换
                FileService.convert_word(file)
                processed_count += 1
            elif file.file_path.lower().endswith(('.pptx', '.ppt')):
                # 调用服务层进行PPT转换
                FileService.convert_ppt(file)
                processed_count += 1
            elif file.file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                # 调用服务层进行图片转换
                FileService.convert_image(file)
                processed_count += 1
            elif FileService.is_archive_file(file.file_path):
                # 调用服务层处理压缩文件
                FileService.extract_and_convert_archive(file)
                processed_count += 1
        
        if processed_count > 0:
            flash(f'{processed_count}个文件处理完成', 'success')
        else:
            flash('没有找到需要处理的文件', 'info')
        
        return redirect(url_for('orders.order_detail', order_number=current_order.order_number))
    
    except Exception as e:
        flash(f'处理文件时出错: {str(e)}', 'error')
        # 尝试重定向回订单详情页
        if 'current_order' in locals() and current_order:
            return redirect(url_for('orders.order_detail', order_number=current_order.order_number))
        return redirect(url_for('main.index'))

# 文件下载路由
@main_bp.route('/download/<int:file_id>')
@login_required
def download_file(file_id):
    """下载文件"""
    # 检查文件类型（上传的或转换的）
    file = FileService.get_uploaded_file(file_id)
    if file:
        return send_from_directory(os.path.dirname(file.file_path),
                                  os.path.basename(file.file_path),
                                  as_attachment=True,
                                  download_name=file.original_filename)
    
    file = FileService.get_converted_file(file_id)
    if file:
        return send_from_directory(os.path.dirname(file.file_path),
                                  os.path.basename(file.file_path),
                                  as_attachment=True,
                                  download_name=file.filename)
    
    flash('文件不存在', 'error')
    return redirect(url_for('orders.index'))

@main_bp.route('/classify-materials', methods=['POST'])
@login_required
def classify_materials():
    """处理材料分类，对文件进行重命名和分类"""
    try:
        # 获取POST数据
        data = request.json
        if not data or 'categorized_files' not in data:
            return jsonify(success=False, message='数据格式错误'), 400
        
        # 获取分类数据
        categorized_files = data.get('categorized_files', {})
        
        # 记录接收到的数据（调试用）
        current_app.logger.info(f"Received classification data: {json.dumps(categorized_files, ensure_ascii=False)}")
        
        # 分类前缀映射表
        category_prefix_map = {
            '申请表&同意书': '01_申请表&同意书',
            '护照首页&证件照': '02_护照首页&证件照',
            '户口本&身份证': '03_户口本&身份证',
            '经济&学历材料': '04_经济&学历材料',
            '关系证明': '05_关系证明',
            '其他材料': '06_其他材料'
        }
        
        # 存储已处理的文件，用于防止重复处理
        processed_files = []
        renamed_files_count = 0
        
        # 处理每个分类中的文件
        for category, files in categorized_files.items():
            # 跳过空分类
            if not files:
                continue
                
            # 获取分类前缀
            prefix = category_prefix_map.get(category, f"00_{category}")
            
            # 处理该分类下的所有文件
            for i, file_item in enumerate(files, 1):
                # 获取原始文件名
                filename = file_item.get('filename')
                
                # 跳过已处理的文件
                if filename in processed_files:
                    continue
                    
                processed_files.append(filename)
                
                # 查找数据库中的文件记录
                file_record = FileRepository.get_converted_file_by_filename(filename)
                if not file_record:
                    current_app.logger.warning(f"文件记录不存在: {filename}")
                    continue
                
                # 构建新文件名: 分类前缀_序号.png
                new_filename = f"{prefix}_{i}.png"
                
                # 获取当前文件路径
                converted_folder = current_app.config.get('CONVERTED_FOLDER')
                order_id = file_record.order_id
                
                # 优先在订单子目录查找
                order_folder = os.path.join(converted_folder, f"order_{order_id}")
                old_file_path = os.path.join(order_folder, filename)
                new_file_path = os.path.join(order_folder, new_filename)
                file_found = False
                
                # 如果订单子目录中找不到，则尝试在根目录查找
                if not os.path.exists(old_file_path):
                    old_file_path = os.path.join(converted_folder, filename)
                    new_file_path = os.path.join(converted_folder, new_filename)
                    
                    # 确保存放的目录存在
                    if not os.path.exists(os.path.dirname(new_file_path)):
                        os.makedirs(os.path.dirname(new_file_path), exist_ok=True)
                
                # 确认文件存在后再进行重命名
                if os.path.exists(old_file_path):
                    file_found = True
                    try:
                        # 如果目标文件已存在，先删除
                        if os.path.exists(new_file_path):
                            os.remove(new_file_path)
                            
                        # 重命名文件
                        shutil.copy2(old_file_path, new_file_path)
                        os.remove(old_file_path)  # 移除旧文件
                    except Exception as e:
                        current_app.logger.error(f"文件重命名失败: {filename} -> {new_filename}, 错误: {str(e)}")
                        continue
                
                # 更新存档路径中的文件
                archive_folder = os.path.join(
                    current_app.config.get('ARCHIVE_FOLDER', ''),
                    'converted',
                    file_record.order.order_number if file_record.order else ''
                )
                old_archive_path = file_record.file_path
                new_archive_path = os.path.join(archive_folder, new_filename)
                
                # 尝试更新存档文件
                try:
                    if os.path.exists(old_archive_path):
                        # 如果目标文件已存在，先删除
                        if os.path.exists(new_archive_path):
                            os.remove(new_archive_path)
                            
                        # 重命名文件
                        shutil.copy2(old_archive_path, new_archive_path)
                        os.remove(old_archive_path)  # 移除旧文件
                except Exception as e:
                    current_app.logger.error(f"存档文件重命名失败: {old_archive_path} -> {new_archive_path}, 错误: {str(e)}")
                
                # 更新数据库记录
                if file_found:
                    try:
                        FileRepository.update_converted_file(file_record.id, {
                            'filename': new_filename,
                            'file_path': new_archive_path
                        })
                        renamed_files_count += 1
                    except Exception as e:
                        current_app.logger.error(f"更新数据库记录失败: {filename} -> {new_filename}, 错误: {str(e)}")
        
        # 返回成功响应
        return jsonify(success=True, message=f'分类保存成功，{renamed_files_count}个文件已重命名')
        
    except Exception as e:
        current_app.logger.error(f"Classification error: {str(e)}", exc_info=True)
        return jsonify(success=False, message=f'处理分类数据时出错: {str(e)}'), 500

# 清空PNG池路由
@main_bp.route('/clear-png-cache', methods=['POST'])
@login_required
def clear_png_cache():
    """清空PNG池（删除所有转换后的PNG文件）"""
    try:
        # 获取订单ID
        order_id = request.form.get('order_id')
        if not order_id:
            flash('请指定要清空PNG池的订单', 'error')
            return redirect(url_for('orders.index'))
            
        order = OrderService.get_order(int(order_id))
        if not order:
            flash('订单不存在', 'error')
            return redirect(url_for('orders.index'))
        
        # 清除订单的所有转换文件
        FileService.clear_converted_files(order.id)
        
        flash('PNG池已清空', 'success')
        return redirect(url_for('orders.order_detail', order_number=order.order_number))
    except Exception as e:
        flash(f'清空PNG池时出错: {str(e)}', 'error')
        return redirect(url_for('orders.index'))

# 文件列表重定向（兼容旧链接）
@main_bp.route('/files')
@login_required
def file_list():
    """文件列表（重定向到订单列表）"""
    flash('文件列表已移至订单管理', 'info')
    return redirect(url_for('orders.index'))

# 清空所有上传文件
@main_bp.route('/delete_all_uploads', methods=['POST'])
@login_required
def delete_all_uploads():
    """清空所有上传文件"""
    try:
        # 获取当前活跃订单
        order = OrderService.get_active_order()
        if not order:
            flash('没有活跃订单', 'error')
            return redirect(url_for('main.index'))
        
        # 清除订单的所有转换文件
        FileService.clear_converted_files(order.id)
        
        # 删除订单的所有上传文件
        files = OrderService.get_order_files(order.id)
        for file in files:
            FileService.delete_uploaded_file(file.id)
        
        flash('所有文件已清空', 'success')
        return redirect(url_for('orders.order_detail', order_number=order.order_number))
    except Exception as e:
        flash(f'清空文件时出错: {str(e)}', 'error')
        # 如果获取不到order_id，返回首页
        if 'order' not in locals() or not order:
            return redirect(url_for('main.index'))
        return redirect(url_for('orders.order_detail', order_number=order.order_number))

# 文件预览路由 - 支持UUID或文件名
@main_bp.route('/preview/<path:filename>')
@login_required
def preview_file(filename):
    """预览文件（主要用于图片）
    
    允许通过文件名或文件UUID进行预览
    UUID格式: 使用数据库中的file_uuid作为唯一不变标识
    """
    try:
        # 获取order_id参数（可选）
        order_id = request.args.get('order_id')
        current_app.logger.info(f"预览文件请求: {filename}, 订单ID: {order_id}")
        
        # 获取order_id参数，用于限定查询范围
        order_id_param = request.args.get('order_id')
        
        # 尝试将filename解析为UUID（数字ID）
        is_uuid = filename.isdigit()
        
        # 根据不同标识符查找文件记录
        converted_file = None
        if is_uuid:
            # 尝试通过UUID查找
            converted_file = FileRepository.get_converted_file_by_id(int(filename))
            current_app.logger.info(f"通过UUID查找文件: {filename}")
        else:
            # 尝试通过文件名查找，优先在指定订单内查找
            if order_id_param:
                # 如果提供了订单ID，则在该订单内查找匹配文件名的文件
                order_files = FileRepository.get_converted_files_by_order(int(order_id_param))
                if order_files:
                    for file in order_files:
                        if file.filename == filename:
                            converted_file = file
                            current_app.logger.info(f"在订单 {order_id_param} 内找到文件: {filename}")
                            break
            
            # 如果在指定订单中没有找到，再尝试全局查找
            if not converted_file:
                converted_file = FileService.get_converted_file_by_filename(filename)
                current_app.logger.info(f"通过全局文件名查找文件: {filename}")
        
        if not converted_file:
            current_app.logger.error(f"找不到文件记录: {filename}")
            return "文件不存在", 404
            
        # 如果指定了order_id，确保文件属于该订单
        if order_id and str(converted_file.order_id) != str(order_id):
            current_app.logger.warning(f"文件 {filename} 不属于订单 {order_id}")
            return "文件不属于当前订单", 403
            
        # 获取文件真实的订单ID
        actual_order_id = str(converted_file.order_id) if converted_file.order_id else None
        
        # 获取所有可能的路径/URL
        file_path = converted_file.file_path  # 公共URL路径
        storage_path = converted_file.storage_path if hasattr(converted_file, 'storage_path') else None  # 物理存储路径
        public_url = converted_file.public_url if hasattr(converted_file, 'public_url') else None  # 直接公共URL
        
        # 如果有存储路径且文件存在，直接从存储路径提供文件
        if storage_path and os.path.exists(storage_path):
            current_app.logger.info(f"从物理存储路径提供文件: {storage_path}")
            file_dir = os.path.dirname(storage_path)
            file_name = os.path.basename(storage_path)
            return send_from_directory(file_dir, file_name, mimetype='image/png')
        
        # 如果有公共URL，直接重定向
        if public_url and public_url.startswith('http'):
            current_app.logger.info(f"重定向到公共URL: {public_url}")
            return redirect(public_url)
        
        # 检查文件路径是否是绝对URL
        if file_path and file_path.startswith('http'):
            # 使用原始URL
            current_app.logger.info(f"重定向到原始URL路径: {file_path}")
            return redirect(file_path)
        
        # 构建转换服务URL
        convert_svc_url = current_app.config.get('CONVERT_SVC_URL', os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081'))
        
        # 提取文件名/路径部分
        filename_only = os.path.basename(converted_file.filename) if not file_path else os.path.basename(urllib.parse.unquote(file_path))
        
        # 获取订单号（查表，不用ID）
        order = OrderService.get_order(int(actual_order_id)) if actual_order_id else None
        order_number = order.order_number if order else None
        
        # 如果有订单号，构建包含订单号的完整URL
        if order_number:
            redirect_url = f"{convert_svc_url}/files/{order_number}/{filename_only}"
            current_app.logger.info(f"重定向到订单子目录URL: {redirect_url}")
            return redirect(redirect_url)
        
        # 最后尝试：直接拼接转换服务的文件路径
        redirect_url = f"{convert_svc_url}/files/{filename_only}"
        current_app.logger.info(f"尝试最后的重定向URL: {redirect_url}")
        return redirect(redirect_url)
    
    except Exception as e:
        current_app.logger.error(f"预览文件时出错: {str(e)}")
        try:
            # 尝试返回错误图片
            placeholder_path = os.path.join(current_app.root_path, 'static', 'img')
            if os.path.exists(os.path.join(placeholder_path, 'error.png')):
                return send_from_directory(placeholder_path, 'error.png', mimetype='image/png')
            else:
                return f"Error: {str(e)}", 500
        except:
            return "Server error", 500

# 添加代理路由，转发文件请求到转换服务
@main_bp.route('/files/<path:filename>')
def file_proxy(filename):
    """代理转发文件请求到转换服务"""
    try:
        # 从转换服务获取文件
        convert_svc_url = current_app.config.get('CONVERT_SVC_URL', os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081'))
        
        # 检查是否包含订单号
        order_id = request.args.get('order_id')
        
        # 如果文件名中没有斜杠，但有订单号参数，则在路径中添加订单号
        if order_id and '/' not in filename:
            file_url = f"{convert_svc_url}/files/{order_id}/{filename}"
            current_app.logger.info(f"访问订单子目录文件: {file_url}")
        else:
            file_url = f"{convert_svc_url}/files/{filename}"
            current_app.logger.info(f"访问文件: {file_url}")
        
        # 使用requests获取文件
        response = requests.get(file_url, stream=True)
        
        if response.status_code == 200:
            # 创建一个Flask响应
            from flask import Response
            
            # 设置相同的headers
            headers = {}
            for name, value in response.headers.items():
                if name.lower() not in ('content-length', 'connection', 'transfer-encoding'):
                    headers[name] = value
                    
            # 返回流式响应
            return Response(
                response.iter_content(chunk_size=10*1024),
                status=response.status_code,
                headers=headers,
                content_type=response.headers.get('content-type', 'image/png')
            )
        else:
            current_app.logger.error(f"从转换服务获取文件失败: {file_url}, 状态码: {response.status_code}")
            
            # 如果第一次尝试失败并且有订单号，尝试不同的组合
            if order_id and '/' not in filename and file_url.endswith(f"/{order_id}/{filename}"):
                # 尝试不使用订单号子目录
                alt_file_url = f"{convert_svc_url}/files/{filename}"
                current_app.logger.info(f"尝试备选路径: {alt_file_url}")
                
                alt_response = requests.get(alt_file_url, stream=True)
                if alt_response.status_code == 200:
                    # 创建一个Flask响应
                    from flask import Response
                    
                    # 返回流式响应
                    return Response(
                        alt_response.iter_content(chunk_size=10*1024),
                        status=alt_response.status_code,
                        headers={k: v for k, v in alt_response.headers.items() if k.lower() not in ('content-length', 'connection', 'transfer-encoding')},
                        content_type=alt_response.headers.get('content-type', 'image/png')
                    )
            
            # 如果仍然找不到，返回错误
            return f"获取文件失败: {response.status_code}", response.status_code
    
    except Exception as e:
        current_app.logger.error(f"代理文件请求时出错: {str(e)}")
        return f"服务器错误: {str(e)}", 500

# 下载所有文件（打包为ZIP）
@main_bp.route('/download_all')
@login_required
def download_all():
    """将所有转换文件打包为ZIP下载"""
    try:
        # 获取订单ID
        order_id = request.args.get('order_id')
        if not order_id:
            flash('请指定要下载文件的订单', 'error')
            return redirect(url_for('orders.index'))
            
        # 根据ID获取订单
        order = OrderService.get_order(int(order_id))
        if not order:
            flash('订单不存在', 'error')
            return redirect(url_for('orders.index'))
        
        # 创建临时目录
        import tempfile
        temp_dir = tempfile.mkdtemp()
        zip_filename = f'files_{order.order_number}.zip'
        zip_path = os.path.join(temp_dir, zip_filename)
        
        # 获取convert-svc服务地址
        convert_svc_url = os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081')
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # 获取订单的转换文件
            converted_files_objs = OrderService.get_order_conversions(order.id)
            
            # 如果没有文件，返回错误
            if not converted_files_objs:
                flash('没有可下载的文件', 'error')
                return redirect(url_for('orders.order_detail', order_number=order.order_number))
            
            # 添加的文件计数
            added_files_count = 0
            
            # 添加文件到ZIP
            for file_obj in converted_files_objs:
                try:
                    # 获取公共URL路径和文件名
                    file_url = file_obj.file_path  # 这可能是一个URL
                    filename = file_obj.filename   # 使用数据库中存储的文件名
                    display_name = file_obj.display_name if hasattr(file_obj, 'display_name') else filename
                    
                    # 获取实际存储路径（如果有）
                    storage_path = file_obj.storage_path if hasattr(file_obj, 'storage_path') else None
                    
                    # 尝试从存储路径获取文件
                    if storage_path and os.path.exists(storage_path):
                        # 使用物理存储路径
                        zipf.write(storage_path, display_name)
                        current_app.logger.info(f"添加文件到ZIP (从存储路径): {storage_path} -> {display_name}")
                        added_files_count += 1
                        continue
                    
                    # 检查原始文件路径是否是本地路径
                    if not file_url.startswith(('http://', 'https://')):
                        if os.path.exists(file_url):
                            # 文件存在于记录的路径中
                            zipf.write(file_url, display_name)
                            current_app.logger.info(f"添加文件到ZIP (本地路径): {file_url} -> {display_name}")
                            added_files_count += 1
                            continue
                    
                        # 检查常见文件位置
                        # 仅当存储路径和直接路径都不可用时才尝试猜测路径                                      
                        converted_folder = current_app.config.get('CONVERTED_FOLDER')
                        
                        # 可能的文件路径列表
                        possible_paths = [
                            # 订单号子目录中的文件
                            os.path.join(converted_folder, order.order_number, filename),
                            # 订单ID子目录中的文件
                            os.path.join(converted_folder, f"order_{order.id}", filename),
                            # 根目录中的文件
                            os.path.join(converted_folder, filename)
                        ]
                        
                        # 检查所有可能的路径
                        file_found = False
                        for path in possible_paths:
                            if os.path.exists(path):
                                zipf.write(path, display_name)
                                current_app.logger.info(f"添加文件到ZIP (找到路径): {path} -> {display_name}")
                                file_found = True
                                added_files_count += 1
                                break
                        
                        if file_found:
                            continue
                    
                    # 如果无法在本地找到，尝试从URL下载
                    try:
                        # 构造合适的URL（如果需要）
                        download_url = file_url
                        if "/files/" in file_url and not file_url.startswith(('http://', 'https://')):
                            # 构造完整URL
                            download_url = f"{convert_svc_url}/files/{file_url}"
                        
                        # 从URL下载文件
                        response = requests.get(download_url, timeout=30)
                        if response.status_code == 200:
                            # 保存到临时文件
                            temp_file_path = os.path.join(temp_dir, filename)
                            with open(temp_file_path, 'wb') as f:
                                f.write(response.content)
                            
                            # 添加到ZIP
                            zipf.write(temp_file_path, display_name)
                            current_app.logger.info(f"添加文件到ZIP (从URL): {download_url} -> {display_name}")
                            added_files_count += 1
                            
                            # 删除临时文件
                            try:
                                os.remove(temp_file_path)
                            except:
                                pass
                        else:
                            current_app.logger.warning(f"无法从URL获取文件: {download_url}, 状态码: {response.status_code}")
                    except Exception as download_error:
                        current_app.logger.error(f"从URL下载文件时出错: {str(download_error)}")
                        
                except Exception as file_error:
                    current_app.logger.error(f"处理文件时出错: {str(file_error)}")
            
            # 如果没有成功添加任何文件
            if added_files_count == 0:
                flash('没有可下载的文件 (所有文件都无法访问)', 'warning')
                # 删除临时目录和空ZIP
                try:
                    os.remove(zip_path)
                    os.rmdir(temp_dir)
                except:
                    pass
                return redirect(url_for('orders.order_detail', order_number=order.order_number))
        
        # 发送文件
        @after_this_request
        def cleanup(response):
            try:
                os.remove(zip_path)
                os.rmdir(temp_dir)
            except Exception as e:
                current_app.logger.error(f"清理临时文件时出错: {str(e)}")
            return response
        
        return send_from_directory(temp_dir, zip_filename, as_attachment=True)
    
    except Exception as e:
        current_app.logger.error(f"下载文件时出错: {str(e)}")
        flash(f'下载文件时出错: {str(e)}', 'error')
        return redirect(url_for('main.index'))

# 通过文件名下载文件
@main_bp.route('/download/by-name/<path:filename>')
@login_required
def download_file_by_name(filename):
    """通过文件名下载文件"""
    try:
        # 获取order_id参数
        order_id = request.args.get('order_id')
        
        # 在数据库中查找文件记录
        converted_file = FileService.get_converted_file_by_filename(filename)
        
        if not converted_file:
            flash(f'文件不存在: {filename}', 'error')
            if order_id:
                return redirect(url_for('orders.order_detail', order_number=order_id))
            return redirect(url_for('main.index'))
            
        # 如果指定了order_id，确保文件属于该订单
        if order_id and str(converted_file.order_id) != str(order_id):
            flash(f'文件不属于当前订单', 'error')
            return redirect(url_for('orders.order_detail', order_number=order_id))
            
        # 检查文件路径是否是URL
        file_path = converted_file.file_path
        if file_path.startswith('http'):
            # 从转换服务下载文件并提供给用户
            try:
                response = requests.get(file_path, stream=True, timeout=30)
                if response.status_code == 200:
                    from flask import Response
                    
                    # 设置下载头
                    headers = {
                        'Content-Disposition': f'attachment; filename="{filename}"'
                    }
                    
                    # 返回流式响应
                    return Response(
                        response.iter_content(chunk_size=10*1024),
                        status=response.status_code,
                        headers=headers,
                        content_type=response.headers.get('content-type', 'image/png')
                    )
                else:
                    flash(f'从转换服务下载文件失败', 'error')
            except Exception as e:
                current_app.logger.error(f"从转换服务下载文件时出错: {str(e)}")
                flash(f'下载文件时出错: {str(e)}', 'error')
        else:
            # 处理旧记录：检查本地文件是否存在
            if os.path.exists(file_path):
                file_dir = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                return send_from_directory(file_dir, file_name, 
                                          as_attachment=True, 
                                          download_name=filename)
            else:
                flash(f'本地文件不存在: {file_path}', 'error')
        
        # 如果出错，重定向回订单详情页或首页
        if order_id:
            return redirect(url_for('orders.order_detail', order_number=order_id))
        return redirect(url_for('main.index'))
        
    except Exception as e:
        current_app.logger.error(f"下载文件时出错: {str(e)}")
        flash(f'下载文件时出错: {str(e)}', 'error')
        if order_id:
            return redirect(url_for('orders.order_detail', order_number=order_id))
        return redirect(url_for('main.index'))

# 通过文件名下载文件
@main_bp.route('/check-converted-files/<int:order_id>')
@login_required
def check_converted_files(order_id):
    """查看订单转换后的文件格式"""
    try:
        # 获取订单的转换后文件
        converted_files = OrderService.get_order_conversions(order_id)
        
        # 记录转换后文件信息
        current_app.logger.info(f"订单 {order_id} 转换后文件数量: {len(converted_files) if converted_files else 0}")
        current_app.logger.info(f"转换后文件类型: {type(converted_files)}")
        
        if converted_files and len(converted_files) > 0:
            sample_file = converted_files[0]
            current_app.logger.info(f"示例文件: {sample_file}, 类型: {type(sample_file)}")
            
            # 检查文件是否存在
            converted_folder = current_app.config.get('CONVERTED_FOLDER', 'Not set')
            filename = os.path.basename(sample_file)
            
            # 先在订单子目录中查找
            order_folder = os.path.join(converted_folder, f"order_{order_id}")
            file_path = os.path.join(order_folder, filename)
            
            # 如果在订单目录找不到，再在根目录中查找
            if not os.path.exists(file_path):
                file_path = os.path.join(converted_folder, filename)
                
            current_app.logger.info(f"示例文件路径: {file_path}")
            current_app.logger.info(f"文件是否存在: {os.path.exists(file_path)}")
        
        # 返回结果
        return jsonify({
            'order_id': order_id,
            'count': len(converted_files) if converted_files else 0,
            'sample': sample_file if converted_files and len(converted_files) > 0 else None,
            'type': str(type(converted_files))
        })
    except Exception as e:
        current_app.logger.error(f"检查转换文件时出错: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

# 删除上传文件路由
@main_bp.route('/delete_upload/<path:filename>', methods=['GET'])
@login_required
def delete_upload(filename):
    """删除上传的文件"""
    try:
        # 从活跃订单中查找对应文件
        order = OrderService.get_active_order()
        if not order:
            flash('没有活跃订单', 'error')
            return redirect(url_for('main.index'))
        
        files = OrderService.get_order_files(order.id)
        file_to_delete = None
        
        # 查找匹配的文件
        for file in files:
            if file.filename == filename or os.path.basename(file.file_path) == filename:
                file_to_delete = file
                break
        
        # 如果找到了文件，则删除它
        if file_to_delete:
            if FileService.delete_uploaded_file(file_to_delete.id):
                flash('文件已删除', 'success')
            else:
                flash('删除文件失败', 'error')
        else:
            flash(f'找不到文件 {filename}', 'error')
        
        # 返回到订单详情页
        return redirect(url_for('orders.order_detail', order_number=order.order_number))
    except Exception as e:
        flash(f'删除文件时出错: {str(e)}', 'error')
        # 如果获取不到order_id，返回首页
        if 'order' not in locals() or not order:
            return redirect(url_for('main.index'))
        return redirect(url_for('orders.order_detail', order_number=order.order_number))

@main_bp.route('/api/files/categorize', methods=['POST'])
@login_required
def categorize_files():
    """
    对文件进行分类，对应分类名称，并执行重命名操作
    请求体：
    {
        "files": [
            {"file_uuid": "abc123", "category": "护照首页", "display_name": "原始文件名.png"},
            {"file_uuid": "def456", "category": "申请表", "display_name": "原始文件名.png"}
        ]
    }
    """
    try:
        data = request.get_json()
        if not data or 'files' not in data:
            return jsonify({"success": False, "message": "请求格式错误"}), 400
        
        files_data = data['files']
        if not files_data or not isinstance(files_data, list):
            return jsonify({"success": False, "message": "文件数据格式错误"}), 400
        
        current_app.logger.info(f"接收到分类请求: {json.dumps(files_data, ensure_ascii=False)}")
        
        results = []
        
        # 获取convert-svc服务地址
        convert_svc_url = os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081')
        
        # 为每个文件处理分类和重命名
        for file_item in files_data:
            # 支持两种格式：新的file_uuid和旧的file_id
            file_uuid = file_item.get('file_uuid') or file_item.get('file_id')
            category = file_item.get('category')
            display_name = file_item.get('display_name')
            
            if not file_uuid or not category:
                results.append({
                    "file_uuid": file_uuid,
                    "success": False,
                    "message": "缺少文件UUID或分类信息"
                })
                continue
                
            current_app.logger.info(f"处理文件分类: UUID={file_uuid}, 分类={category}")
            
            # 首先尝试通过UUID查询文件记录
            file_record = FileRepository.get_converted_file_by_id(file_uuid) \
                if file_uuid.isdigit() else None
                
            # 如果找不到，尝试通过文件名查询（兼容旧接口）
            if not file_record:
                file_record = FileRepository.get_converted_file_by_filename(file_uuid)
                
            if not file_record:
                current_app.logger.error(f"文件记录不存在: {file_uuid}")
                results.append({
                    "file_uuid": file_uuid,
                    "success": False,
                    "message": "文件记录不存在"
                })
                continue
            
            # 获取订单号
            order = OrderService.get_order(file_record.order_id)
            order_number = order.order_number if order else None
            
            # 检查文件是否存在
            # 改为使用数据库中记录的路径，而不是根据文件名猜测
            original_path = file_record.file_path
            storage_path = file_record.storage_path if hasattr(file_record, 'storage_path') else None
            
            # 获取当前分类下的序号
            category_files = FileRepository.get_converted_files_by_order(file_record.order_id)
            # 根据文件名前缀来判断分类
            category_count = sum(1 for f in category_files if f.filename.startswith(f"{category}_"))
            
            # 保留原始文件扩展名
            file_ext = os.path.splitext(file_record.filename)[1]
            
            # 获取订单号的短标识（取最后8位或更少）
            order_suffix = ""
            if order_number and len(order_number) > 8:
                order_suffix = order_number[-8:]  # 取订单号的最后8位作为后缀
            elif order_number:
                order_suffix = order_number  # 如果订单号小于8位，使用完整订单号
            
            # 生成新的显示文件名，加入订单号后缀
            new_display_name = f"{category}_{category_count + 1}_{order_suffix}{file_ext}"
            
            current_app.logger.info(f"生成新文件名: {new_display_name}, 分类计数: {category_count}, 订单后缀: {order_suffix}")
            
            # 确保使用正确的路径格式
            if "/files/" in original_path:
                # 提取文件名
                filename_only = os.path.basename(urllib.parse.unquote(original_path))
                # 使用订单号构建正确的路径
                original_path = f"{order_number}/{filename_only}"
            
            current_app.logger.info(f"原始文件路径: {original_path}, 订单号: {order_number}")
            
            # 调用转换服务API进行文件重命名
            rename_response = requests.post(
                f"{convert_svc_url}/api/rename",
                json={
                    "original_path": original_path,
                    "new_name": new_display_name,
                    "order_id": order_number  # 使用订单号而不是订单ID
                }
            )
            
            current_app.logger.info(f"重命名API响应状态码: {rename_response.status_code}")
            current_app.logger.info(f"重命名API响应内容: {rename_response.text}")
            
            if rename_response.status_code != 200:
                results.append({
                    "file_uuid": file_uuid,
                    "success": False,
                    "message": f"调用重命名服务失败: {rename_response.text}"
                })
                continue
            
            rename_data = rename_response.json()
            if not rename_data.get('success'):
                results.append({
                    "file_uuid": file_uuid,
                    "success": False,
                    "message": f"重命名失败: {rename_data.get('message')}"
                })
                continue
            
            # 更新数据库记录
            try:
                # 保存旧路径用于通知归档服务
                old_path = file_record.file_path
                old_name = file_record.filename
                
                # 新的公共URL路径
                new_public_url = rename_data.get('new_url')
                
                # 更新数据库记录
                update_data = {
                    'filename': new_display_name,  # 更新显示名称
                    'file_path': new_public_url,   # 更新公共URL
                    'category': category           # 添加分类信息
                }
                
                # 如果有storage_path字段，同时更新物理存储路径
                if hasattr(file_record, 'storage_path') and rename_data.get('new_path'):
                    update_data['storage_path'] = rename_data.get('new_path')
                
                # 更新记录，保留原始ID不变
                FileRepository.update_converted_file(
                    file_record.id,
                    **update_data
                )
                
                # 记录操作日志
                current_app.logger.info(f"已将文件 {old_name} (ID: {file_record.id}) 分类为 '{category}'，新路径: {new_public_url}")
                
                # 异步通知archive-svc更新归档
                try:
                    archive_svc_url = os.environ.get('ARCHIVE_SVC_URL')
                    if archive_svc_url:
                        # 获取当前应用实例
                        app = current_app._get_current_object()
                        
                        # 使用线程异步通知，不阻塞主流程，同时传递应用上下文
                        thread = threading.Thread(
                            target=notify_archive_service,
                            args=(app, archive_svc_url, file_record.id, file_record.order_id, old_path, new_public_url)
                        )
                        thread.daemon = True  # 设置为守护线程，主程序退出时自动结束
                        thread.start()
                except Exception as e:
                    current_app.logger.error(f"启动通知归档服务线程失败: {str(e)}")
                
                results.append({
                    "file_uuid": str(file_record.id),  # 始终返回数据库ID作为唯一标识
                    "old_id": file_uuid,               # 返回原始传入的ID用于前端匹配
                    "success": True,
                    "message": "文件分类成功",
                    "new_url": new_public_url,
                    "category": category,
                    "display_name": new_display_name
                })
            except Exception as db_error:
                # 使用SQLAlchemy的会话回滚
                db.session.rollback()
                current_app.logger.error(f"更新数据库失败: {str(db_error)}")
                results.append({
                    "file_uuid": file_uuid,
                    "success": False,
                    "message": f"更新数据库失败: {str(db_error)}"
                })
        
        # 判断整体操作是否成功
        all_success = all(result.get('success', False) for result in results)
        
        return jsonify({
            "success": all_success,
            "message": "文件分类处理完成",
            "results": results
        })
    
    except Exception as e:
        current_app.logger.error(f"文件分类错误: {str(e)}")
        return jsonify({"success": False, "message": f"服务器处理错误: {str(e)}"}), 500

# 辅助函数：异步通知归档服务
def notify_archive_service(app, archive_url, file_id, order_id, old_url, new_url):
    """异步通知归档服务文件重命名事件
    
    Args:
        app: Flask应用实例，用于创建应用上下文
        archive_url: 归档服务的URL
        file_id: 文件ID
        order_id: 订单ID
        old_url: 旧的文件URL
        new_url: 新的文件URL
    """
    # 在线程中创建应用上下文
    with app.app_context():
        try:
            app.logger.info(f"开始通知归档服务，文件ID: {file_id}")
            
            response = requests.post(
                f"{archive_url}/update",
                json={
                    "file_id": file_id,
                    "order_id": order_id,
                    "old_url": old_url,
                    "new_url": new_url,
                    "operation": "rename"
                },
                timeout=10  # 设置超时以避免永久阻塞
            )
            
            if response.status_code == 200:
                app.logger.info(f"通知归档服务成功，文件ID: {file_id}")
            else:
                app.logger.error(f"归档服务返回错误: {response.status_code} - {response.text}")
        
        except requests.RequestException as e:
            app.logger.error(f"通知归档服务网络错误: {str(e)}")
        except Exception as e:
            app.logger.error(f"通知归档服务异常: {str(e)}")
