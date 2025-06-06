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
            current_app.logger.info(f"开始转换PDF: {file.filename}")
            
            # 使用convert_to_images进行转换
            output_paths = FileService.convert_to_images(
                file_path=file.file_path,
                output_dir=os.path.join(current_app.config['CONVERTED_FOLDER'], f"pdf_{int(time.time())}"),
                file_type="pdf",
                dpi=300,
                source_hash=file.file_hash,
                order_id=file.order_id
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
            current_app.logger.error(f"转换PDF文件失败: {file.filename}, 错误: {str(e)}")
            raise RuntimeError(f"PDF转换失败: {str(e)}")

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
            current_app.logger.info(f"开始转换Word文档: {file.filename}")
            
            # 使用convert_to_images进行转换
            output_paths = FileService.convert_to_images(
                file_path=file.file_path,
                output_dir=os.path.join(current_app.config['CONVERTED_FOLDER'], f"word_{int(time.time())}"),
                file_type="docx",
                dpi=300,
                source_hash=file.file_hash,
                order_id=file.order_id
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
            current_app.logger.error(f"转换Word文档失败: {file.filename}, 错误: {str(e)}")
            raise RuntimeError(f"Word转换失败: {str(e)}")

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
            current_app.logger.info(f"开始转换PPT: {file.filename}")
            
            # 使用convert_to_images进行转换
            output_paths = FileService.convert_to_images(
                file_path=file.file_path,
                output_dir=os.path.join(current_app.config['CONVERTED_FOLDER'], f"ppt_{int(time.time())}"),
                file_type="pptx",
                dpi=300,
                source_hash=file.file_hash,
                order_id=file.order_id
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
            current_app.logger.error(f"转换PPT文件失败: {file.filename}, 错误: {str(e)}")
            raise RuntimeError(f"PPT转换失败: {str(e)}")

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
            current_app.logger.info(f"开始转换图片: {file.filename}")
            
            # 使用convert_to_images进行转换
            output_paths = FileService.convert_to_images(
                file_path=file.file_path,
                output_dir=os.path.join(current_app.config['CONVERTED_FOLDER'], f"img_{int(time.time())}"),
                file_type="image",
                source_hash=file.file_hash,
                order_id=file.order_id
            )
            
            # 保存转换后的文件记录
            if output_paths and len(output_paths) > 0:
                filename = os.path.basename(output_paths[0])
                converted_file = FileService.save_converted_file(
                    filename=filename,
                    file_path=output_paths[0],
                    order_id=file.order_id,
                    source_file_id=file.id,
                    source_hash=file.file_hash
                )
                return converted_file
            return None
        except Exception as e:
            current_app.logger.error(f"转换图片文件失败: {file.filename}, 错误: {str(e)}")
            raise RuntimeError(f"图片转换失败: {str(e)}")

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
            current_app.logger.info(f"开始处理压缩包: {file.filename}")
            
            # 提取压缩包
            extract_dir = FileService.extract_archive(file.file_path)
            if not extract_dir:
                raise RuntimeError("无法提取压缩包内容")
            
            # 遍历提取的文件
            for root, dirs, files in os.walk(extract_dir):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    file_lower = filename.lower()
                    
                    # 计算文件哈希值
                    file_hash = FileService.calculate_file_hash(file_path)
                    current_app.logger.info(f"处理压缩包内文件: {filename}")
                    
                    try:
                        output_dir = os.path.join(
                            current_app.config['CONVERTED_FOLDER'],
                            f"zip_{int(time.time())}_{os.path.splitext(filename)[0]}"
                        )
                        
                        # 根据文件类型进行转换
                        if file_lower.endswith('.pdf'):
                            output_paths = FileService.convert_to_images(
                                file_path=file_path,
                                output_dir=output_dir,
                                file_type="pdf",
                                dpi=300,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path,
                                order_id=file.order_id
                            )
                        elif file_lower.endswith(('.docx', '.doc')):
                            output_paths = FileService.convert_to_images(
                                file_path=file_path,
                                output_dir=output_dir,
                                file_type="docx",
                                dpi=300,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path,
                                order_id=file.order_id
                            )
                        elif file_lower.endswith(('.pptx', '.ppt')):
                            output_paths = FileService.convert_to_images(
                                file_path=file_path,
                                output_dir=output_dir,
                                file_type="pptx",
                                dpi=300,
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path,
                                order_id=file.order_id
                            )
                        elif file_lower.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')):
                            output_paths = FileService.convert_to_images(
                                file_path=file_path,
                                output_dir=output_dir,
                                file_type="image",
                                source_hash=file_hash,
                                from_zip=True,
                                zip_path=file.file_path,
                                order_id=file.order_id
                            )
                        else:
                            # 跳过不支持的文件类型
                            current_app.logger.info(f"跳过不支持的文件类型: {filename}")
                            continue
                        
                        # 保存转换后的文件记录
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
                    
                    except Exception as e:
                        current_app.logger.error(f"转换压缩包内文件失败: {filename}, 错误: {str(e)}")
                        # 继续处理下一个文件
            
            # 清理临时目录
            try:
                import shutil
                shutil.rmtree(extract_dir)
            except Exception as e:
                current_app.logger.warning(f"清理临时目录失败: {str(e)}")
                
            return converted_files
        except Exception as e:
            current_app.logger.error(f"处理压缩包时出错: {file.filename}, 错误: {str(e)}")
            raise RuntimeError(f"压缩包处理失败: {str(e)}")

    @staticmethod
    def archive_file(file_path, category="general", description=None, tags=None):
        """将文件归档到归档服务
        
        Args:
            file_path: 文件路径
            category: 文件分类
            description: 文件描述
            tags: 文件标签列表
            
        Returns:
            归档成功返回归档文件ID，否则返回None
        """
        if not os.path.exists(file_path):
            current_app.logger.error(f"归档文件不存在: {file_path}")
            return None
        
        # 获取归档服务URL
        archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8088/api/v1/archive')
        
        # 健康检查
        try:
            health_check = requests.get(f"{archive_svc_url.split('/archive')[0]}/health", timeout=2)
            if health_check.status_code != 200:
                current_app.logger.error(f"归档服务不可用: {health_check.status_code}")
                return None
        except Exception as e:
            current_app.logger.error(f"连接归档服务失败: {str(e)}")
            return None

    @staticmethod
    def get_file_by_hash(file_hash):
        """根据文件哈希值从归档服务获取文件信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件信息字典，如果未找到则返回None
        """
        if not file_hash:
            return None
        
        # 获取归档服务URL
        archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8088/api/v1/archive')
        
        try:
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
        """从归档服务下载文件
        
        Args:
            file_id: 归档文件ID
            target_path: 目标保存路径，如果为None则使用临时目录
            
        Returns:
            下载成功返回文件路径，否则返回None
        """
        if not file_id:
            return None
        
        # 获取归档服务URL
        archive_svc_url = current_app.config.get('ARCHIVE_SVC_URL', 'http://localhost:8088/api/v1/archive')
        
        try:
            response = requests.get(f"{archive_svc_url}/files/{file_id}/download", timeout=30, stream=True)
            
            if response.status_code == 200:
                if target_path:
                    # 保存到文件
                    with open(target_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    return target_path
                else:
                    # 返回文件内容
                    return response.content
            else:
                current_app.logger.error(f"从归档服务下载文件失败: {response.status_code}")
                return None
        
        except Exception as e:
            current_app.logger.error(f"下载归档文件失败: {str(e)}")
            return None

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
            
            # 不再创建数据库记录，只返回文件信息
            return file_data
        
        except Exception as e:
            current_app.logger.error(f"存储文件时出错: {str(e)}")
            raise e

    @staticmethod
    def convert_to_images(file_path, output_dir=None, file_type=None, pages=None, dpi=200, 
                          source_hash=None, from_zip=False, zip_path=None, order_id=None):
        """
        将文件转换为PNG图片，使用Go转换服务
        
        Args:
            file_path: 文件路径
            output_dir: 输出目录
            file_type: 文件类型
            pages: 要转换的页面列表
            dpi: 转换DPI
            source_hash: 源文件哈希值
            from_zip: 是否从ZIP提取的文件
            zip_path: ZIP文件路径
            order_id: 订单ID，用于按订单隔离存储
            
        Returns:
            转换后的图片路径列表
            
        Raises:
            RuntimeError: 转换服务不可用或转换失败
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
            
            # 检查转换服务可用性
            convert_svc_url = current_app.config.get('CONVERT_SVC_URL', 'http://localhost:8081')
            
            if not convert_client.health_check():
                current_app.logger.error(f"转换服务不可用: {convert_svc_url}")
                raise RuntimeError(f"转换服务不可用，请确保转换服务已启动并运行在 {convert_svc_url}")

            # 准备转换参数
            payload = {
                "file_path": file_path,
                "output_dir": output_dir,
                "dpi": dpi
            }
            
            if pages:
                payload["pages"] = pages

            # 调用转换服务
            current_app.logger.info(f"调用Go转换服务处理文件: {file_path}")
            response = requests.post(f"{convert_svc_url}/api/convert", json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    converted_files = result.get("files", [])
                    current_app.logger.info(f"使用转换服务成功转换文件: {file_path} -> {len(converted_files)} 个文件")

                    # 存储规范化的文件路径列表，用于返回
                    final_converted_files = []
                    file_records = []
                    
                    # 确保converted目录存在
                    converted_folder = current_app.config['CONVERTED_FOLDER']
                    
                    # 如果提供了订单ID，则按订单ID创建子目录
                    if order_id:
                        converted_folder = os.path.join(converted_folder, f"order_{order_id}")
                    
                    os.makedirs(converted_folder, exist_ok=True)
                    
                    # 从文件路径获取基本名称（不包含扩展名）
                    base_filename = os.path.splitext(os.path.basename(file_path))[0]
                    
                    for image_path in converted_files:
                        try:
                            # 获取原始转换后文件的文件名
                            original_filename = os.path.basename(image_path)
                            
                            # 创建在converted目录中的目标路径
                            target_path = os.path.join(converted_folder, original_filename)
                            
                            # 复制文件到converted目录
                            if os.path.exists(image_path):
                                shutil.copy2(image_path, target_path)
                                current_app.logger.info(f"已复制转换文件: {image_path} -> {target_path}")
                                
                                # 计算文件哈希值
                                file_hash = FileService.calculate_file_hash(target_path)
                                
                                # 收集文件信息
                                file_data = {
                                    'filename': original_filename,
                                    'file_path': target_path,  # 使用新路径
                                    'file_type': 'image/png',
                                    'file_hash': file_hash,
                                    'source_hash': source_hash,
                                    'from_zip': from_zip,
                                    'zip_path': zip_path
                                }
                                file_records.append(file_data)
                                
                                # 添加到最终返回的文件列表
                                final_converted_files.append(target_path)
                            else:
                                current_app.logger.error(f"转换后的文件不存在: {image_path}")
                        except Exception as e:
                            current_app.logger.error(f"处理转换后的文件时出错: {image_path}, 错误: {str(e)}")
                    
                    # 返回已复制到converted目录的文件路径
                    return final_converted_files
                else:
                    error_msg = result.get("error", "未知错误")
                    current_app.logger.error(f"转换服务处理文件失败: {error_msg}")
                    raise RuntimeError(f"文件转换失败: {error_msg}")
            else:
                current_app.logger.error(f"转换服务HTTP错误: {response.status_code}, {response.text}")
                raise RuntimeError(f"转换服务返回错误状态码: {response.status_code}")
            
        except Exception as e:
            current_app.logger.error(f"转换文件时出错: {file_path}, 错误: {str(e)}")
            raise RuntimeError(f"文件转换失败: {str(e)}") 