import os
import uuid
import hashlib
import shutil
import zipfile
import rarfile
import requests
from werkzeug.utils import secure_filename
from flask import current_app
import logging
import time
from datetime import datetime
import mimetypes

from src.repositories.file_repo import FileRepository
from src.repositories.order_repo import OrderRepository
from src.utils.file_utils import convert_pdf_to_png, convert_docx_to_png, convert_pptx_to_png, convert_image_to_png
from src.utils.convert_client import convert_client

class FileService:
    """文件服务类，处理与文件相关的业务逻辑"""
    
    @staticmethod
    def get_uploaded_file(file_id):
        """根据ID获取上传的文件"""
        return FileRepository.get_uploaded_file(file_id)
    
    @staticmethod
    def get_uploaded_file_by_filename(filename):
        """根据文件名获取上传的文件"""
        return FileRepository.get_uploaded_file_by_filename(filename)
    
    @staticmethod
    def get_converted_file(file_id):
        """根据ID获取转换的文件"""
        return FileRepository.get_converted_file(file_id)
    
    @staticmethod
    def get_converted_file_by_filename(filename):
        """根据文件名获取转换的文件"""
        return FileRepository.get_converted_file_by_filename(filename)
    
    @staticmethod
    def calculate_file_hash(file_path):
        """计算文件SHA256哈希值"""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            chunk = f.read(8192)
            while chunk:
                hasher.update(chunk)
                chunk = f.read(8192)
        return hasher.hexdigest()
    
    @staticmethod
    def save_uploaded_file(file, order_id):
        """保存上传的文件
        
        Args:
            file: Flask文件对象
            order_id: 订单ID
            
        Returns:
            保存成功返回上传文件对象，否则返回None
        """
        if not file or not file.filename:
            return None
        
        # 获取订单对象
        order = OrderRepository.get_by_id(order_id)
        if not order:
            return None
        
        # 使用安全的文件名，同时支持中文
        original_filename = file.filename
        # 先只替换windows文件名不支持的字符，而不是用werkzeug的secure_filename（会去除中文）
        safe_filename = original_filename
        for char in r'<>:"/\|?*':
            safe_filename = safe_filename.replace(char, '_')
        
        # 确保文件名唯一
        base, ext = os.path.splitext(safe_filename)
        unique_filename = f"{base}_{uuid.uuid4().hex[:8]}{ext}"
        
        # 保存到上传目录
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # 同时保存到订单存档目录
        archive_folder = os.path.join(
            current_app.config['ARCHIVE_FOLDER'],
            'uploads',
            order.order_number
        )
        os.makedirs(archive_folder, exist_ok=True)
        archive_path = os.path.join(archive_folder, unique_filename)
        
        try:
            shutil.copy2(file_path, archive_path)
        except Exception as e:
            current_app.logger.error(f"存档上传文件时出错: {unique_filename}, 错误: {str(e)}")
        
        # 获取文件大小和类型
        file_size = os.path.getsize(file_path)
        file_type = FileService.detect_file_type(file_path)
        
        # 计算文件哈希值
        file_hash = FileService.calculate_file_hash(file_path)
        
        # 创建上传文件记录
        return FileRepository.create_uploaded_file(
            filename=unique_filename,
            original_filename=original_filename,
            file_path=archive_path,  # 使用存档路径，这样即使工作目录被清空，还能恢复文件
            file_size=file_size,
            file_type=file_type,
            file_hash=file_hash,
            order_id=order_id
        )
    
    @staticmethod
    def save_converted_file(filename, file_path, order_id, source_file_id=None, 
                           source_hash=None, from_zip=False, zip_path=None):
        """保存转换后的文件记录
        
        Args:
            filename: 文件名
            file_path: 文件路径
            order_id: 订单ID
            source_file_id: 源文件ID
            source_hash: 源文件哈希值
            from_zip: 是否来自压缩包
            zip_path: 压缩包路径
            
        Returns:
            保存成功返回转换文件对象，否则返回None
        """
        # 获取订单对象
        order = OrderRepository.get_by_id(order_id)
        if not order:
            return None
        
        # 同时保存到订单存档目录
        archive_folder = os.path.join(
            current_app.config['ARCHIVE_FOLDER'],
            'converted',
            order.order_number
        )
        os.makedirs(archive_folder, exist_ok=True)
        archive_path = os.path.join(archive_folder, filename)
        
        try:
            if os.path.exists(file_path):
                shutil.copy2(file_path, archive_path)
        except Exception as e:
            current_app.logger.error(f"存档转换文件时出错: {filename}, 错误: {str(e)}")
        
        # 创建转换文件记录
        return FileRepository.create_converted_file(
            filename=filename,
            file_path=archive_path,  # 使用存档路径
            order_id=order_id,
            source_file_id=source_file_id,
            source_hash=source_hash,
            from_zip=from_zip,
            zip_path=zip_path
        )
    
    @staticmethod
    def delete_uploaded_file(file_id):
        """删除上传的文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        file = FileRepository.get_uploaded_file(file_id)
        if not file:
            return False
        
        # 删除物理文件
        try:
            # 删除上传目录中的文件
            upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
            if os.path.exists(upload_path):
                os.remove(upload_path)
            
            # 删除存档目录中的文件（可选）
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        except Exception as e:
            current_app.logger.error(f"删除文件时出错: {file.filename}, 错误: {str(e)}")
        
        # 删除数据库记录
        return FileRepository.delete_uploaded_file(file_id)
    
    @staticmethod
    def delete_converted_file(file_id):
        """删除转换后的文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        file = FileRepository.get_converted_file(file_id)
        if not file:
            return False
        
        # 删除物理文件
        try:
            # 删除转换目录中的文件
            converted_path = os.path.join(current_app.config['CONVERTED_FOLDER'], file.filename)
            if os.path.exists(converted_path):
                os.remove(converted_path)
            
            # 删除存档目录中的文件（可选）
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        except Exception as e:
            current_app.logger.error(f"删除转换文件时出错: {file.filename}, 错误: {str(e)}")
        
        # 删除数据库记录
        return FileRepository.delete_converted_file(file_id)
    
    @staticmethod
    def clear_converted_files(order_id):
        """清除指定订单的所有转换文件
        
        Args:
            order_id: 订单ID
            
        Returns:
            清除成功返回True，否则返回False
        """
        files = FileRepository.get_converted_files_by_order(order_id)
        
        # 删除物理文件
        for file in files:
            try:
                converted_path = os.path.join(current_app.config['CONVERTED_FOLDER'], file.filename)
                if os.path.exists(converted_path):
                    os.remove(converted_path)
            except Exception as e:
                current_app.logger.error(f"清除转换文件时出错: {file.filename}, 错误: {str(e)}")
        
        # 删除数据库记录
        FileRepository.delete_converted_files_by_order(order_id)
        return True
    
    @staticmethod
    def detect_file_type(file_path):
        """检测文件类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类型字符串
        """
        # 根据扩展名判断
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext in ['.pdf']:
            return 'pdf'
        elif ext in ['.docx', '.doc']:
            return 'docx' if ext == '.docx' else 'doc'
        elif ext in ['.pptx', '.ppt']:
            return 'pptx' if ext == '.pptx' else 'ppt'
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']:
            return 'image'
        elif ext in ['.zip']:
            return 'zip'
        elif ext in ['.rar']:
            return 'rar'
        
        # 尝试通过文件头判断
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                
                # PDF: %PDF
                if header.startswith(b'%PDF'):
                    return 'pdf'
                
                # ZIP: PK\x03\x04
                if header.startswith(b'PK\x03\x04'):
                    return 'zip'
                
                # RAR: Rar!\x1A\x07\x00
                if header.startswith(b'Rar!\x1A\x07\x00'):
                    return 'rar'
                
                # JPEG: \xFF\xD8\xFF
                if header.startswith(b'\xFF\xD8\xFF'):
                    return 'image'
                
                # PNG: \x89PNG\r\n\x1A\n
                if header.startswith(b'\x89PNG\r\n\x1A\n'):
                    return 'image'
                
                # Office文档（docx, pptx等）也是ZIP格式，但需要进一步判断
                if header.startswith(b'PK\x03\x04'):
                    return 'zip'  # 默认返回zip，具体类型在解压后判断
        except:
            pass
        
        return 'unknown'
    
    @staticmethod
    def is_archive_file(file_path):
        """检查是否为压缩文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是压缩文件返回True，否则返回False
        """
        file_type = FileService.detect_file_type(file_path)
        return file_type in ['zip', 'rar']
    
    @staticmethod
    def extract_archive(archive_path, extract_to=None):
        """解压缩文件
        
        Args:
            archive_path: 压缩文件路径
            extract_to: 解压目标路径，如果为None则解压到临时目录
            
        Returns:
            解压目录路径
        """
        import tempfile
        
        # 如果没有指定解压目录，则创建临时目录
        if extract_to is None:
            extract_to = tempfile.mkdtemp()
        
        file_type = FileService.detect_file_type(archive_path)
        
        try:
            if file_type == 'zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    # 处理编码问题
                    for zip_info in zip_ref.infolist():
                        try:
                            # 尝试使用utf-8解码
                            filename = zip_info.filename.encode('cp437').decode('utf-8')
                        except:
                            # 如果失败，尝试使用系统默认编码
                            try:
                                filename = zip_info.filename.encode('cp437').decode('gbk')
                            except:
                                # 如果都失败，使用原始名称
                                filename = zip_info.filename
                        
                        # 创建安全的文件名
                        safe_filename = filename
                        for char in r'<>:"/\|?*':
                            safe_filename = safe_filename.replace(char, '_')
                        
                        # 更新文件名
                        if safe_filename != zip_info.filename:
                            # 对于文件名有问题的情况，单独提取并重命名
                            source = zip_ref.read(zip_info.filename)
                            target_path = os.path.join(extract_to, safe_filename)
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as f:
                                f.write(source)
                        else:
                            # 常规情况，提取到临时目录
                            zip_ref.extract(zip_info, extract_to)
            
            elif file_type == 'rar':
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    # 处理编码问题
                    for rar_info in rar_ref.infolist():
                        try:
                            # 尝试处理文件名，解决编码问题
                            filename = rar_info.filename
                            # 创建安全的文件名
                            safe_filename = filename
                            for char in r'<>:"/\|?*':
                                safe_filename = safe_filename.replace(char, '_')
                            
                            # 更新文件名
                            if safe_filename != rar_info.filename:
                                # 对于文件名有问题的情况，单独提取并重命名
                                source = rar_ref.read(rar_info.filename)
                                target_path = os.path.join(extract_to, safe_filename)
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                with open(target_path, 'wb') as f:
                                    f.write(source)
                            else:
                                # 常规情况，提取到临时目录
                                rar_ref.extract(rar_info, extract_to)
                        except Exception as e:
                            current_app.logger.error(f"处理RAR内文件名时出错: {str(e)}")
                            # 尝试以二进制方式提取文件
                            try:
                                safe_filename = f"extracted_file_{hash(rar_info.filename)}"
                                source = rar_ref.read(rar_info.filename)
                                target_path = os.path.join(extract_to, safe_filename)
                                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                                with open(target_path, 'wb') as f:
                                    f.write(source)
                            except:
                                pass
            
            return extract_to
        except Exception as e:
            current_app.logger.error(f"解压文件时出错: {archive_path}, 错误: {str(e)}")
            return None

    # 新增方法：转换PDF文件
    @staticmethod
    def convert_pdf(file):
        """转换PDF文件到PNG格式
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        converted_files = []
        try:
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            current_app.logger.info(f"使用Go转换服务转换PDF: {file.filename}")
            output_paths = convert_client.convert_pdf_to_png(
                file.file_path,
                current_app.config['CONVERTED_FOLDER']
            )
            
            # 保存转换后的文件记录
            if output_paths:
                for path in output_paths:
                    filename = os.path.basename(path)
                    converted_file = FileService.save_converted_file(
                        filename=filename,
                        file_path=path,
                        order_id=file.order_id,
                        source_file_id=file.id,
                        source_hash=file.file_hash
                    )
                    if converted_file:
                        converted_files.append(converted_file)
            
            return converted_files
        except Exception as e:
            current_app.logger.error(f"转换PDF文件时出错: {file.filename}, 错误: {str(e)}")
            return []

    # 新增方法：转换Word文档
    @staticmethod
    def convert_word(file):
        """转换Word文档到PNG格式
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        converted_files = []
        try:
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            current_app.logger.info(f"使用Go转换服务转换Word: {file.filename}")
            output_paths = convert_client.convert_docx_to_png(
                file.file_path,
                current_app.config['CONVERTED_FOLDER']
            )
            
            # 保存转换后的文件记录
            if output_paths:
                for path in output_paths:
                    filename = os.path.basename(path)
                    converted_file = FileService.save_converted_file(
                        filename=filename,
                        file_path=path,
                        order_id=file.order_id,
                        source_file_id=file.id,
                        source_hash=file.file_hash
                    )
                    if converted_file:
                        converted_files.append(converted_file)
            
            return converted_files
        except Exception as e:
            current_app.logger.error(f"转换Word文档时出错: {file.filename}, 错误: {str(e)}")
            return []

    # 新增方法：转换PPT文件
    @staticmethod
    def convert_ppt(file):
        """转换PPT文件到PNG格式
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        converted_files = []
        try:
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            current_app.logger.info(f"使用Go转换服务转换PPT: {file.filename}")
            output_paths = convert_client.convert_pptx_to_png(
                file.file_path,
                current_app.config['CONVERTED_FOLDER']
            )
            
            # 保存转换后的文件记录
            if output_paths:
                for path in output_paths:
                    filename = os.path.basename(path)
                    converted_file = FileService.save_converted_file(
                        filename=filename,
                        file_path=path,
                        order_id=file.order_id,
                        source_file_id=file.id,
                        source_hash=file.file_hash
                    )
                    if converted_file:
                        converted_files.append(converted_file)
            
            return converted_files
        except Exception as e:
            current_app.logger.error(f"转换PPT文件时出错: {file.filename}, 错误: {str(e)}")
            return []

    # 新增方法：转换图片文件
    @staticmethod
    def convert_image(file):
        """转换图片文件到标准PNG格式
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象，失败返回None
        """
        try:
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            current_app.logger.info(f"使用Go转换服务转换图片: {file.filename}")
            output_path = convert_client.convert_image_to_png(
                file.file_path,
                current_app.config['CONVERTED_FOLDER']
            )
            
            # 保存转换后的文件记录
            if output_path:
                filename = os.path.basename(output_path)
                converted_file = FileService.save_converted_file(
                    filename=filename,
                    file_path=output_path,
                    order_id=file.order_id,
                    source_file_id=file.id,
                    source_hash=file.file_hash
                )
                return converted_file
            return None
        except Exception as e:
            current_app.logger.error(f"转换图片文件时出错: {file.filename}, 错误: {str(e)}")
            return None

    # 新增方法：提取并转换压缩包中的文件
    @staticmethod
    def extract_and_convert_archive(file):
        """提取压缩包中的文件并转换
        
        Args:
            file: 上传的文件对象（压缩包）
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        converted_files = []
        try:
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            # 提取压缩包
            extract_dir = FileService.extract_archive(file.file_path)
            if not extract_dir:
                return []
            
            # 遍历提取的文件
            for root, dirs, files in os.walk(extract_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    
                    # 计算文件哈希值
                    file_hash = FileService.calculate_file_hash(file_path)
                    
                    # 根据文件类型进行转换
                    if file_path.lower().endswith('.pdf'):
                        output_paths = convert_client.convert_pdf_to_png(
                            file_path,
                            current_app.config['CONVERTED_FOLDER']
                        )
                        for path in output_paths:
                            out_filename = os.path.basename(path)
                            converted_file = FileService.save_converted_file(
                                filename=out_filename,
                                file_path=path,
                                order_id=file.order_id,
                                source_file_id=file.id,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path
                            )
                            if converted_file:
                                converted_files.append(converted_file)
                    
                    elif file_path.lower().endswith(('.docx', '.doc')):
                        output_paths = convert_client.convert_docx_to_png(
                            file_path,
                            current_app.config['CONVERTED_FOLDER']
                        )
                        for path in output_paths:
                            out_filename = os.path.basename(path)
                            converted_file = FileService.save_converted_file(
                                filename=out_filename,
                                file_path=path,
                                order_id=file.order_id,
                                source_file_id=file.id,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path
                            )
                            if converted_file:
                                converted_files.append(converted_file)
                    
                    elif file_path.lower().endswith(('.pptx', '.ppt')):
                        output_paths = convert_client.convert_pptx_to_png(
                            file_path,
                            current_app.config['CONVERTED_FOLDER']
                        )
                        for path in output_paths:
                            out_filename = os.path.basename(path)
                            converted_file = FileService.save_converted_file(
                                filename=out_filename,
                                file_path=path,
                                order_id=file.order_id,
                                source_file_id=file.id,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path
                            )
                            if converted_file:
                                converted_files.append(converted_file)
                    
                    elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                        output_path = convert_client.convert_image_to_png(
                            file_path,
                            current_app.config['CONVERTED_FOLDER']
                        )
                        out_filename = os.path.basename(output_path)
                        converted_file = FileService.save_converted_file(
                            filename=out_filename,
                            file_path=output_path,
                            order_id=file.order_id,
                            source_file_id=file.id,
                            source_hash=file_hash,
                            from_zip=True,
                            zip_path=file.file_path
                        )
                        if converted_file:
                            converted_files.append(converted_file)
            
            # 清理临时目录
            try:
                import shutil
                shutil.rmtree(extract_dir)
            except:
                pass
                
            return converted_files
        except Exception as e:
            current_app.logger.error(f"处理压缩包时出错: {file.filename}, 错误: {str(e)}")
            return []

    @staticmethod
    def archive_file(file_path, category="general", description=None, tags=None):
        """
        归档文件到archive-svc服务
        
        Args:
            file_path: 文件路径
            category: 文件分类
            description: 文件描述
            tags: 文件标签列表
            
        Returns:
            字典包含归档状态和信息
        """
        try:
            # 检查archive-svc服务是否可用
            archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8000/api/v1/archive')
            
            try:
                # 尝试检查服务是否在线
                health_check = requests.get(f"{archive_svc_url.split('/archive')[0]}/health", timeout=2)
                if health_check.status_code != 200:
                    current_app.logger.warning(f"Archive服务健康检查失败: {health_check.status_code}")
                    return {"success": False, "message": "归档服务不可用"}
            except requests.RequestException as e:
                current_app.logger.warning(f"无法连接到Archive服务: {str(e)}")
                return {"success": False, "message": "无法连接到归档服务"}
            
            # 准备请求数据
            files = {'file': open(file_path, 'rb')}
            data = {'category': category}
            
            if description:
                data['description'] = description
                
            if tags and isinstance(tags, list):
                for i, tag in enumerate(tags):
                    data[f'tags'] = tag
            
            # 发送请求
            response = requests.post(f"{archive_svc_url}/files", files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "message": "文件归档成功",
                    "file_id": result.get('file', {}).get('id'),
                    "file_hash": result.get('file', {}).get('sha256_hash'),
                    "stored_path": result.get('file', {}).get('file_path')
                }
            else:
                error_msg = f"归档服务返回错误: {response.status_code}"
                if response.content:
                    try:
                        error_data = response.json()
                        error_msg = f"{error_msg}, {error_data.get('message', '')}"
                    except:
                        pass
                current_app.logger.error(error_msg)
                return {"success": False, "message": error_msg}
        
        except Exception as e:
            current_app.logger.error(f"文件归档失败: {str(e)}")
            return {"success": False, "message": f"文件归档失败: {str(e)}"}

    @staticmethod
    def get_file_by_hash(file_hash):
        """
        通过哈希值从archive-svc获取文件信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件信息字典或None
        """
        try:
            # 检查archive-svc服务是否可用
            archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8000/api/v1/archive')
            
            # 发送请求
            response = requests.get(f"{archive_svc_url}/files/hash/{file_hash}", timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('file')
            elif response.status_code != 404:  # 如果不是404（文件不存在），记录错误
                current_app.logger.error(f"从归档服务获取文件失败: {response.status_code}")
            
            return None
        
        except Exception as e:
            current_app.logger.error(f"通过哈希值查找文件失败: {str(e)}")
            return None

    @staticmethod
    def download_archived_file(file_id, target_path=None):
        """
        从归档服务下载文件
        
        Args:
            file_id: 文件ID
            target_path: 目标保存路径，如果为None则返回文件内容
            
        Returns:
            成功时：如果target_path为None，返回文件内容；否则返回True
            失败时：返回False
        """
        try:
            # 检查archive-svc服务是否可用
            archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8000/api/v1/archive')
            
            # 发送请求
            response = requests.get(f"{archive_svc_url}/files/{file_id}/download", timeout=30, stream=True)
            
            if response.status_code == 200:
                if target_path:
                    # 保存到文件
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return True
                else:
                    # 返回文件内容
                    return response.content
            else:
                current_app.logger.error(f"从归档服务下载文件失败: {response.status_code}")
                return False
        
        except Exception as e:
            current_app.logger.error(f"下载归档文件失败: {str(e)}")
            return False

    @staticmethod
    def store_file(uploaded_file, file_dir, file_type=None, filename=None):
        """
        存储上传的文件
        
        Args:
            uploaded_file: 上传的文件对象
            file_dir: 文件存储目录
            file_type: 文件类型（可选）
            filename: 自定义文件名（可选）
            
        Returns:
            存储后的文件信息字典
        """
        try:
            if filename is None:
                filename = secure_filename(uploaded_file.filename)
            
            # 确保文件目录存在
            os.makedirs(file_dir, exist_ok=True)
            
            # 生成唯一文件名
            unique_filename = f"{int(time.time())}_{filename}"
            file_path = os.path.join(file_dir, unique_filename)
            
            # 保存文件
            uploaded_file.save(file_path)
            
            # 计算文件哈希值
            file_hash = FileService.calculate_file_hash(file_path)
            
            # 尝试归档文件
            archive_result = FileService.archive_file(file_path, 
                                                    category="uploads", 
                                                    description=f"上传于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 如果归档成功，使用归档路径作为备份
            if archive_result and archive_result.get("success"):
                archived_path = archive_result.get("stored_path")
                archived_hash = archive_result.get("file_hash")
                archived_id = archive_result.get("file_id")
                current_app.logger.info(f"文件已归档: {archived_path}, ID: {archived_id}")
            else:
                archived_path = None
                archived_hash = None
                archived_id = None
                
                # 仅当归档失败时才复制到归档目录
                # 创建归档文件夹（按日期分类）
                archive_folder = os.path.join(
                    current_app.config['ARCHIVE_FOLDER'], 
                    datetime.now().strftime('%Y-%m-%d')
                )
                os.makedirs(archive_folder, exist_ok=True)
                archive_path = os.path.join(archive_folder, unique_filename)
                
                # 复制文件到归档目录
                shutil.copy2(file_path, archive_path)
                current_app.logger.info(f"文件已本地归档: {archive_path}")
            
            # 创建文件记录
            file_data = {
                'filename': filename,
                'file_path': file_path,
                'file_type': file_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream',
                'file_hash': file_hash,
                'archived_path': archived_path,
                'archived_hash': archived_hash or file_hash,
                'archived_id': archived_id
            }
            
            # 保存到数据库
            file_id = FileRepository.create_file(file_data)
            
            # 添加ID到文件数据
            file_data['id'] = file_id
            
            return file_data
        
        except Exception as e:
            current_app.logger.error(f"存储文件时出错: {str(e)}")
            raise e

    @staticmethod
    def convert_to_images(file_path, output_dir=None, file_type=None, pages=None, dpi=200, 
                          source_hash=None, from_zip=False, zip_path=None):
        """
        将文件转换为PNG图片
        
        Args:
            file_path: 文件路径
            output_dir: 输出目录
            file_type: 文件类型
            pages: 要转换的页面列表
            dpi: 转换DPI
            source_hash: 源文件哈希值
            from_zip: 是否从ZIP提取的文件
            zip_path: ZIP文件路径
            
        Returns:
            转换后的图片路径列表
        """
        try:
            if not os.path.exists(file_path):
                current_app.logger.error(f"文件不存在: {file_path}")
                return []
            
            # 如果没有指定输出目录，创建一个默认的
            if output_dir is None:
                # 创建归档文件夹（按日期分类）
                archive_folder = os.path.join(
                    current_app.config['ARCHIVE_FOLDER'],
                    datetime.now().strftime('%Y-%m-%d')
                )
                os.makedirs(archive_folder, exist_ok=True)
                
                # 从文件路径中提取文件名
                filename = os.path.basename(file_path)
                
                # 输出目录
                output_dir = os.path.join(
                    current_app.config['CONVERTED_FOLDER'],
                    os.path.splitext(filename)[0]
                )
                os.makedirs(output_dir, exist_ok=True)
            
            if not convert_client.health_check():
                raise RuntimeError("转换服务不可用")

            convert_svc_url = current_app.config.get('CONVERT_SVC_URL', 'http://localhost:8080/api')

            payload = {
                "file_path": file_path,
                "output_dir": output_dir,
                "dpi": dpi
            }

            response = requests.post(f"{convert_svc_url}/convert", json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    converted_files = result.get("files", [])
                    current_app.logger.info(f"使用Go服务成功转换文件: {file_path}")

                    file_records = []
                    for image_path in converted_files:
                        file_hash = FileService.calculate_file_hash(image_path)

                        file_data = {
                            'filename': os.path.basename(image_path),
                            'file_path': image_path,
                            'file_type': 'image/png',
                            'file_hash': file_hash,
                            'source_hash': source_hash,
                            'from_zip': from_zip,
                            'zip_path': zip_path
                        }

                        file_id = FileRepository.create_file(file_data)
                        file_data['id'] = file_id
                        file_records.append(file_data)

                    return converted_files

            raise RuntimeError("文件转换失败")
        
        except Exception as e:
            current_app.logger.error(f"转换文件时出错: {file_path}, 错误: {str(e)}")
            return [] 