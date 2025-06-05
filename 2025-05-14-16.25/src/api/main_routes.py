from flask import Blueprint, render_template, redirect, url_for, request, session, flash, send_from_directory, jsonify, abort, current_app
from werkzeug.utils import secure_filename
import os
import uuid
from functools import wraps
import json
import zipfile
from flask import after_this_request

from src.api import main_bp
from src.services.admin_service import AdminService
from src.services.file_service import FileService
from src.services.order_service import OrderService
from src.utils.decorators import login_required

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
        
        # 优先使用表单中传递的order_id，如果没有则使用活跃订单或创建新订单
        order = None
        order_id = request.form.get('order_id')
        
        if order_id:
            order = OrderService.get_order(int(order_id))
        
        # 如果没有找到指定订单，获取活跃订单，如果没有则创建新订单
        if not order:
            order = OrderService.get_active_order()
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
            return redirect(url_for('orders.order_detail', order_id=order.id))
        else:
            flash('文件上传失败', 'error')
    
    return render_template('upload.html')

# 处理文件路由
@main_bp.route('/process', methods=['POST'])
@login_required
def process():
    """处理已上传的文件"""
    try:
        # 获取指定的订单ID，如果没有则使用当前活跃订单
        order_id = request.form.get('order_id')
        current_order = None
        
        if order_id:
            current_order = OrderService.get_order(int(order_id))
        else:
            current_order = OrderService.get_active_order()
        
        if not current_order:
            flash('没有找到有效订单，请先创建一个订单')
            return redirect(url_for('main.index'))
        
        # 获取所有已选中的文件ID
        selected_file_ids = request.form.getlist('selected_files[]')
        
        # 如果没有提交selected_files[]，获取当前订单中的所有文件
        if not selected_file_ids:
            # 获取当前订单中的所有文件
            files = OrderService.get_order_files(current_order.id)
            
            if not files:
                flash('当前订单没有可处理的文件，请先上传文件')
                return redirect(url_for('orders.order_detail', order_id=current_order.id))
            
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
        
        return redirect(url_for('orders.order_detail', order_id=current_order.id))
    
    except Exception as e:
        flash(f'处理文件时出错: {str(e)}', 'error')
        # 尝试重定向回订单详情页
        if 'current_order' in locals() and current_order:
            return redirect(url_for('orders.order_detail', order_id=current_order.id))
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
    """处理材料分类，暂时实现"""
    try:
        # 获取POST数据
        data = request.json
        if not data or 'categorized_files' not in data:
            return jsonify(success=False, message='数据格式错误'), 400
        
        # 这里只是临时返回成功，实际应该处理分类数据并保存
        # categorized_files = data.get('categorized_files', {})
        
        # 记录接收到的数据（调试用）
        print(f"Received classification data: {json.dumps(data, ensure_ascii=False)}")
        
        # 返回成功响应
        return jsonify(success=True, message='分类保存成功')
        
    except Exception as e:
        print(f"Classification error: {str(e)}")
        return jsonify(success=False, message=f'处理分类数据时出错: {str(e)}'), 500

# 清空PNG池路由
@main_bp.route('/clear-png-cache', methods=['POST'])
@login_required
def clear_png_cache():
    """清空PNG池（删除所有转换后的PNG文件）"""
    try:
        # 获取当前活跃订单
        order = OrderService.get_active_order()
        if not order:
            flash('没有活跃订单', 'error')
            return redirect(url_for('main.index'))
        
        # 清除订单的所有转换文件
        FileService.clear_converted_files(order.id)
        
        flash('PNG池已清空', 'success')
        return redirect(url_for('orders.order_detail', order_id=order.id))
    except Exception as e:
        flash(f'清空PNG池时出错: {str(e)}', 'error')
        # 如果获取不到order_id，返回首页
        if not order:
            return redirect(url_for('main.index'))
        return redirect(url_for('orders.order_detail', order_id=order.id))

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
        return redirect(url_for('orders.order_detail', order_id=order.id))
    except Exception as e:
        flash(f'清空文件时出错: {str(e)}', 'error')
        # 如果获取不到order_id，返回首页
        if 'order' not in locals() or not order:
            return redirect(url_for('main.index'))
        return redirect(url_for('orders.order_detail', order_id=order.id))

# 文件预览路由
@main_bp.route('/preview/<path:filename>')
@login_required
def preview_file(filename):
    """预览文件（主要用于图片）"""
    try:
        # 获取order_id参数（可选）
        order_id = request.args.get('order_id')
        
        # 调试信息
        converted_folder = current_app.config.get('CONVERTED_FOLDER', 'Not set')
        current_app.logger.info(f"CONVERTED_FOLDER: {converted_folder}")
        current_app.logger.info(f"预览文件: {filename}")
        
        # 验证文件是否属于指定订单
        if order_id:
            # 查找文件记录
            converted_file = FileService.get_converted_file_by_filename(filename)
            if converted_file and str(converted_file.order_id) != str(order_id):
                current_app.logger.warning(f"文件 {filename} 不属于订单 {order_id}")
                return "文件不属于当前订单", 403
        
        # 尝试从转换目录获取文件
        preview_path = os.path.join(converted_folder, filename)
        current_app.logger.info(f"完整路径: {preview_path}")
        current_app.logger.info(f"文件是否存在: {os.path.exists(preview_path)}")
        
        # 如果找不到文件，记录错误
        if not os.path.exists(preview_path):
            current_app.logger.error(f"找不到预览文件: {preview_path}")
            # 返回一个占位图片
            placeholder_path = os.path.join(current_app.root_path, 'static', 'img')
            if os.path.exists(os.path.join(placeholder_path, 'not-found.png')):
                return send_from_directory(placeholder_path, 'not-found.png', mimetype='image/png')
            else:
                # 创建一个简单的响应
                return "File not found", 404
        
        # 返回文件
        return send_from_directory(
            converted_folder,
            filename,
            mimetype='image/png'
        )
    except Exception as e:
        current_app.logger.error(f"预览文件时出错: {str(e)}")
        try:
            # 尝试返回错误图片
            placeholder_path = os.path.join(current_app.root_path, 'static', 'img')
            if os.path.exists(os.path.join(placeholder_path, 'error.png')):
                return send_from_directory(placeholder_path, 'error.png', mimetype='image/png')
            else:
                # 创建一个简单的响应
                return f"Error: {str(e)}", 500
        except:
            return "Server error", 500

# 下载所有文件（打包为ZIP）
@main_bp.route('/download_all')
@login_required
def download_all():
    """将所有转换文件打包为ZIP下载"""
    try:
        # 获取当前活跃订单
        order = OrderService.get_active_order()
        if not order:
            flash('没有活跃订单', 'error')
            return redirect(url_for('main.index'))
        
        # 创建临时目录
        import tempfile
        temp_dir = tempfile.mkdtemp()
        zip_filename = f'files_{order.order_number}.zip'
        zip_path = os.path.join(temp_dir, zip_filename)
        
        # 创建ZIP文件
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            # 获取订单的转换文件
            converted_files_objs = OrderService.get_order_conversions(order.id)
            
            # 如果没有文件，返回错误
            if not converted_files_objs:
                flash('没有可下载的文件', 'error')
                return redirect(url_for('orders.order_detail', order_id=order.id))
            
            # 添加文件到ZIP
            for file_obj in converted_files_objs:
                file_path = file_obj.file_path
                if os.path.exists(file_path):
                    # 添加到zip时使用相对路径，使解压缩更干净
                    filename = os.path.basename(file_path)
                    zipf.write(file_path, filename)
                    current_app.logger.info(f"添加文件到ZIP: {file_path} -> {filename}")
                else:
                    current_app.logger.warning(f"文件不存在，跳过: {file_path}")
        
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
        # 调试信息
        converted_folder = current_app.config.get('CONVERTED_FOLDER', 'Not set')
        current_app.logger.info(f"CONVERTED_FOLDER: {converted_folder}")
        current_app.logger.info(f"下载文件: {filename}")
        
        # 获取order_id参数
        order_id = request.args.get('order_id')
        current_app.logger.info(f"Order ID: {order_id}")
        
        # 构建文件路径
        file_path = os.path.join(converted_folder, filename)
        current_app.logger.info(f"完整路径: {file_path}")
        current_app.logger.info(f"文件是否存在: {os.path.exists(file_path)}")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            flash(f'文件不存在: {filename}', 'error')
            # 如果提供了order_id参数，则重定向到订单详情页
            if order_id:
                return redirect(url_for('orders.order_detail', order_id=order_id))
            return redirect(url_for('main.index'))
        
        # 返回文件
        return send_from_directory(
            converted_folder,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"下载文件时出错: {str(e)}")
        flash(f'下载文件时出错: {str(e)}', 'error')
        if order_id:
            return redirect(url_for('orders.order_detail', order_id=order_id))
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
            file_path = os.path.join(converted_folder, sample_file)
            current_app.logger.info(f"示例文件路径: {file_path}")
            current_app.logger.info(f"文件是否存在: {os.path.exists(file_path)}")
        
        # 返回结果
        return jsonify({
            'order_id': order_id,
            'count': len(converted_files) if converted_files else 0,
            'files': converted_files
        })
    except Exception as e:
        current_app.logger.error(f"检查转换后文件时出错: {str(e)}")
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
        return redirect(url_for('orders.order_detail', order_id=order.id))
    except Exception as e:
        flash(f'删除文件时出错: {str(e)}', 'error')
        # 如果获取不到order_id，返回首页
        if 'order' not in locals() or not order:
            return redirect(url_for('main.index'))
        return redirect(url_for('orders.order_detail', order_id=order.id))
