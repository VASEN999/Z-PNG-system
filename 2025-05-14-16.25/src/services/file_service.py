import os
import uuid
import hashlib
import shutil
import zipfile
import rarfile
import requests
import functools
from werkzeug.utils import secure_filename
from flask import current_app, flash
import logging
import time
from datetime import datetime
import mimetypes

from src.repositories.file_repo import FileRepository
from src.repositories.order_repo import OrderRepository
from src.utils.file_utils import convert_pdf_to_png, convert_docx_to_png, convert_pptx_to_png, convert_image_to_png
from src.utils.convert_client import convert_client

# 文件类型策略表
FILE_TYPE_MAP = {
    'pdf': {
        'mime': 'application/pdf',
        'extensions': ['.pdf'],
        'check': lambda header: header.startswith(b'%PDF'),
        'converter': lambda client, path, **kwargs: client.convert_pdf_to_png(path, **kwargs),
    },
    'docx': {
        'mime': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'extensions': ['.docx', '.doc'],
        'check': None,
        'converter': lambda client, path, **kwargs: client.convert_docx_to_png(path, **kwargs),
    },
    'pptx': {
        'mime': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'extensions': ['.pptx', '.ppt'],
        'check': None,
        'converter': lambda client, path, **kwargs: client.convert_pptx_to_png(path, **kwargs),
    },
    'image': {
        'mime': 'image/*',
        'extensions': ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'],
        'check': lambda header: (header.startswith(b'\xFF\xD8\xFF') or  # JPEG
                                header.startswith(b'\x89PNG\r\n\x1A\n')),  # PNG
        'converter': lambda client, path, **kwargs: client.convert_image_to_png(path, **kwargs),
    },
    'zip': {
        'mime': 'application/zip',
        'extensions': ['.zip'],
        'check': lambda header: header.startswith(b'PK\x03\x04'),
    },
    'rar': {
        'mime': 'application/x-rar-compressed',
        'extensions': ['.rar'],
        'check': lambda header: header.startswith(b'Rar!\x1A\x07\x00'),
    },
}

# 装饰器：记录异常并返回默认值
def log_exceptions(error_message, default_return=None):
    """处理异常并记录日志的装饰器
    
    Args:
        error_message: 记录到日志的错误信息前缀
        default_return: 发生异常时返回的默认值
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                current_app.logger.error(f"{error_message}: {str(e)}")
                if isinstance(default_return, Exception):
                    raise default_return from e
                return default_return
        return wrapper
    return decorator

class ArchiveService:
    """归档服务类，处理与文件归档相关的业务逻辑"""
    
    @staticmethod
    @log_exceptions("归档文件时出错", default_return=None)
    def archive_file(file_path, category="general", description=None, tags=None):
        """将文件归档
        
        Args:
            file_path: 文件路径
            category: 文件分类
            description: 文件描述
            tags: 文件标签列表
            
        Returns:
            归档成功返回归档信息字典，否则返回None
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
            
        # TODO: 实现文件归档逻辑，调用归档服务
        # 暂时返回None，表示归档失败，让FileService继续使用本地归档
        return None
    
    @staticmethod
    @log_exceptions("查找文件时出错", default_return=None)
    def get_file_by_hash(file_hash):
        """根据文件哈希值获取文件信息
        
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
    @log_exceptions("下载文件时出错", default_return=None)
    def download_file(file_id, target_path=None):
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
        """计算文件的SHA-256哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件哈希值（16进制字符串）
        """
        try:
            hasher = hashlib.sha256()
            with open(file_path, 'rb') as f:
                # 分块读取文件，避免大文件一次性读入内存
                for chunk in iter(lambda: f.read(4096), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            current_app.logger.error(f"计算文件哈希出错: {str(e)}")
            return None
    
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
    def save_converted_file(filename, file_url, order_id, source_file_id=None, 
                           source_hash=None, from_zip=False, zip_path=None):
        """保存转换后的文件记录
        
        Args:
            filename: 文件名
            file_url: 文件URL（由转换服务提供）
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
        
        # 创建转换文件记录，直接使用转换服务提供的URL
        return FileRepository.create_converted_file(
            filename=filename,
            file_path=file_url,  # 使用URL而非本地路径
            order_id=order_id,
            source_file_id=source_file_id,
            source_hash=source_hash,
            from_zip=from_zip,
            zip_path=zip_path
        )

    # 新增方法：将转换服务返回的URL列表保存为转换文件记录
    @staticmethod
    def save_converted_files_from_urls(file_urls, order_id, source_file_id=None, 
                                     source_hash=None, from_zip=False, zip_path=None):
        """将转换服务返回的URL列表保存为转换文件记录
        
        Args:
            file_urls: 转换服务返回的文件URL列表
            order_id: 订单ID
            source_file_id: 源文件ID
            source_hash: 源文件哈希值
            from_zip: 是否来自压缩包
            zip_path: 压缩包路径
            
        Returns:
            保存成功返回转换文件对象列表，失败返回空列表
        """
        if not file_urls:
            return []
            
        converted_files = []
        for file_url in file_urls:
            # 从URL中提取文件名
            filename = os.path.basename(file_url.split('/')[-1])
            # 保存记录
            converted_file = FileService.save_converted_file(
                filename=filename,
                file_url=file_url,
                order_id=order_id,
                source_file_id=source_file_id,
                source_hash=source_hash,
                from_zip=from_zip,
                zip_path=zip_path
            )
            if converted_file:
                converted_files.append(converted_file)
                
        return converted_files

    @staticmethod
    def delete_uploaded_file(file_id):
        """删除上传的文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        file = FileRepository.get_uploaded_file(file_id)
        return FileService._delete_file_record(
            file, 
            current_app.config['UPLOAD_FOLDER'], 
            FileRepository.delete_uploaded_file
        )
    
    @staticmethod
    def delete_converted_file(file_id):
        """删除转换后的文件
        
        Args:
            file_id: 文件ID
            
        Returns:
            删除成功返回True，否则返回False
        """
        file = FileRepository.get_converted_file(file_id)
        return FileService._delete_file_record(
            file, 
            current_app.config['CONVERTED_FOLDER'], 
            FileRepository.delete_converted_file
        )
    
    @staticmethod
    @log_exceptions("删除文件时出错", default_return=False)
    def _delete_file_record(file, base_dir, repo_delete_func):
        """统一的文件删除方法
        
        Args:
            file: 文件记录对象
            base_dir: 文件基础目录
            repo_delete_func: 仓库删除函数
            
        Returns:
            删除成功返回True，否则返回False
        """
        if not file:
            return False
            
        # 删除物理文件
        file_path = os.path.join(base_dir, file.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除存档文件（如存在）
        if os.path.exists(file.file_path) and file.file_path != file_path:
            os.remove(file.file_path)
        
        # 删除数据库记录
        return repo_delete_func(file.id)
    
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
        
        # 优先通过扩展名检查
        for file_type, specs in FILE_TYPE_MAP.items():
            if ext in specs['extensions']:
                return file_type
        
        # 如果扩展名不明确，尝试通过文件头判断
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)
                
                # 遍历所有文件类型，检查文件头
                for file_type, specs in FILE_TYPE_MAP.items():
                    check_func = specs.get('check')
                    if check_func and check_func(header):
                        return file_type
        except Exception as e:
            current_app.logger.error(f"检测文件类型时出错: {str(e)}")
        
        return 'unknown'
    
    @staticmethod
    def _is_file_type(file_path, file_type):
        """检查文件是否为指定类型
        
        Args:
            file_path: 文件路径
            file_type: 要检查的文件类型
            
        Returns:
            是指定类型返回True，否则返回False
        """
        return FileService.detect_file_type(file_path) == file_type
    
    @staticmethod
    def _is_pdf(file_path):
        """检查文件是否为PDF格式"""
        return FileService._is_file_type(file_path, 'pdf')
    
    @staticmethod
    def _is_word(file_path):
        """检查文件是否为Word文档"""
        file_type = FileService.detect_file_type(file_path)
        return file_type == 'docx' or file_type == 'doc'
    
    @staticmethod
    def _is_ppt(file_path):
        """检查文件是否为PPT文档"""
        file_type = FileService.detect_file_type(file_path)
        return file_type == 'pptx' or file_type == 'ppt'
    
    @staticmethod
    def _is_image(file_path):
        """检查文件是否为图片"""
        return FileService._is_file_type(file_path, 'image')
    
    @staticmethod
    def is_archive_file(file_path):
        """检查是否为压缩文件"""
        file_type = FileService.detect_file_type(file_path)
        return file_type == 'zip' or file_type == 'rar'
    
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
        """转换PDF文件到PNG图片
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        return FileService._convert_file_generic(file, "pdf")

    # 新增方法：转换Word文件
    @staticmethod
    def convert_word(file):
        """转换Word文件到PNG图片
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        return FileService._convert_file_generic(file, "docx")

    # 新增方法：转换PPT文件
    @staticmethod
    def convert_ppt(file):
        """转换PPT文件到PNG图片
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        return FileService._convert_file_generic(file, "pptx")
            
    # 修改方法：转换图片文件
    @staticmethod
    def convert_image(file):
        """转换图片文件到标准PNG格式
        
        Args:
            file: 上传的文件对象
            
        Returns:
            转换成功返回转换后的文件对象，失败返回None
        """
        converted_files = FileService._convert_file_generic(file, "image")
        if converted_files and len(converted_files) > 0:
            return converted_files[0]  # 返回第一个文件
        return None
        
    # 新增：通用文件转换模板方法
    @staticmethod
    @log_exceptions("转换文件失败")
    def _convert_file_generic(file, file_type):
        """通用文件转换模板方法
        
        Args:
            file: 上传的文件对象
            file_type: 文件类型 (pdf, docx, pptx, image)
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        current_app.logger.info(f"开始转换{file_type}文件: {file.filename}")
        
        # 使用convert_to_images进行转换
        output_urls = FileService.convert_to_images(
            file_path=file.file_path,
            output_dir=None,  # 不再使用本地输出目录
            file_type=file_type,
            source_hash=file.file_hash,
            order_id=file.order_id
        )
        
        # 保存转换后的文件记录
        if output_urls and len(output_urls) > 0:
            return FileService.save_converted_files_from_urls(
                file_urls=output_urls,
                order_id=file.order_id,
                source_file_id=file.id,
                source_hash=file.file_hash
            )
        return []

    # 新增方法：提取并转换压缩包中的文件
    @staticmethod
    @log_exceptions("提取并转换压缩包时出错", default_return=[])
    def extract_and_convert_archive(file, depth=0, max_depth=3):
        """提取压缩包中的文件并转换
        
        Args:
            file: 上传的文件对象（压缩包）或内部压缩包的路径
            depth: 当前处理的嵌套深度，用于限制递归
            max_depth: 最大允许的递归深度，防止无限递归
            
        Returns:
            转换成功返回转换后的文件对象列表，失败返回空列表
        """
        # 防止过深的递归
        if depth > max_depth:
            current_app.logger.warning(f"达到最大递归深度 {max_depth}，停止处理更深层次的压缩包")
            return []
            
        converted_files = []
        
        # 处理文件对象和字符串路径的情况
        if isinstance(file, str):
            file_path = file
            file_hash = FileService.calculate_file_hash(file_path)
            file_name = os.path.basename(file_path)
            order_id = None
            parent_id = None
            parent_file_id = None
            current_app.logger.info(f"处理内部压缩包: {file_name}, 嵌套深度: {depth}")
        elif isinstance(file, dict):
            # 处理自定义字典对象（内部压缩包）
            file_path = file.get('file_path')
            file_hash = file.get('file_hash') or FileService.calculate_file_hash(file_path)
            file_name = file.get('filename') or os.path.basename(file_path)
            order_id = file.get('order_id')
            parent_id = file.get('parent_id')
            parent_file_id = file.get('id')
            current_app.logger.info(f"处理内部压缩包: {file_name}, 嵌套深度: {depth}, 使用订单ID: {order_id}")
        else:
            # 处理数据库模型对象（顶层压缩包）
            file_path = file.file_path
            file_hash = file.file_hash
            file_name = file.filename
            order_id = file.order_id
            parent_id = None
            parent_file_id = getattr(file, 'id', None)
            current_app.logger.info(f"开始处理压缩包: {file_name}, 嵌套深度: {depth}")

        # 提取压缩包
        extract_dir = FileService.extract_archive(file_path)
        if not extract_dir:
            raise RuntimeError(f"无法提取压缩包内容: {file_name}")
        
        try:
            # 获取压缩包哈希值，用作父文件标识符
            zip_hash = file_hash
            
            # 获取订单对象（如果适用）
            order_number = None
            if order_id is not None:
                from src.services.order_service import OrderService
                order = OrderService.get_order(order_id)
                order_number = order.order_number if order else str(order_id)
                current_app.logger.info(f"压缩包关联订单: {order_number}")
            
            # 遍历提取的文件
            file_counter = 1  # 添加计数器确保文件名唯一
            for root, dirs, files in os.walk(extract_dir):
                for filename in files:
                    # 跳过隐藏文件和系统文件
                    if filename.startswith('.') or filename.startswith('__'):
                        current_app.logger.info(f"跳过隐藏/系统文件: {filename}")
                        continue
                        
                    # 获取文件完整路径
                    inner_file_path = os.path.join(root, filename)
                    
                    # 计算文件哈希值，用于生成源文件标识符
                    inner_file_hash = FileService.calculate_file_hash(inner_file_path)
                    if inner_file_hash:
                        current_app.logger.info(f"文件哈希值: {inner_file_hash[:10]}...")
                    
                    # 生成唯一源文件ID，组合哈希值和计数器
                    source_id = f"{inner_file_hash[:6]}-{file_counter}" if inner_file_hash else f"file-{file_counter}"
                    current_app.logger.info(f"生成唯一ID: {source_id} (文件 {file_counter}/{len(files)})")
                    file_counter += 1
                    
                    # 检测文件类型
                    file_type = FileService.detect_file_type(inner_file_path)
                    current_app.logger.info(f"检测文件类型: {inner_file_path} -> {file_type}")
                    
                    # 处理嵌套压缩包
                    if file_type in ['zip', 'rar'] and depth < max_depth:
                        current_app.logger.info(f"发现嵌套压缩包: {filename}, 开始递归处理 (深度 {depth+1})")
                        
                        # 在递归处理内部压缩包前，创建一个内部压缩包的临时文件记录对象
                        inner_archive = {
                            'file_path': inner_file_path,
                            'file_hash': inner_file_hash,
                            'filename': filename,
                            'order_id': order_id,  # 传递原始订单ID
                            'id': None  # 内部压缩包没有数据库ID
                        }
                        
                        # 修改：递归处理内部压缩包时传递父压缩包的order_id
                        # 创建包含order_id的自定义对象，确保传递订单ID到内部压缩包处理
                        inner_file_with_order = {
                            'file_path': inner_file_path,
                            'file_hash': inner_file_hash,
                            'filename': filename,
                            'order_id': order_id  # 传递原始订单ID
                        }
                        inner_results = FileService.extract_and_convert_archive(inner_file_with_order, depth + 1, max_depth)
                        
                        if inner_results and len(inner_results) > 0:
                            # 这里我们不需要在内部压缩包处理时将结果添加到converted_files
                            # 内部压缩包处理完成后会返回处理结果，我们只需要记录和报告一下
                            current_app.logger.info(f"内部压缩包 {filename} 处理完成，生成了 {len(inner_results)} 个转换文件")
                            
                            # 只有在最外层调用（depth=0）时才将结果添加到数据库记录
                            if depth == 0 and order_id is not None:
                                # 更新文件记录的层次关系
                                for inner_file in inner_results:
                                    # 这里我们可以添加一些元数据，如嵌套路径信息
                                    pass
                                                    
                                # 添加到总结果集
                                converted_files.extend(inner_results)
                        else:
                            current_app.logger.warning(f"内部压缩包 {filename} 处理未返回任何结果")
                    
                    # 处理常规可转换文件
                    elif file_type in ['pdf', 'docx', 'pptx', 'image']:
                        current_app.logger.info(f"转换文件: {filename}, 类型: {file_type}, 使用源ID: {source_id}, 父ID: {zip_hash}")
                        
                        # 使用转换工具处理文件
                        converted_urls = FileService.convert_to_images(
                            inner_file_path,
                            file_type=file_type,
                            source_hash=source_id, 
                            order_id=order_id,
                            parent_id=zip_hash
                        )
                        
                        # 保存转换后的文件记录（仅当有订单ID且在最外层时）
                        if converted_urls and len(converted_urls) > 0:
                            current_app.logger.info(f"文件 {filename} 成功转换为 {len(converted_urls)} 个文件")
                            
                            # 只有在有订单ID且处于最外层压缩包处理时才保存到数据库
                            if order_id is not None and depth == 0:
                                saved_files = FileService.save_converted_files_from_urls(
                                    converted_urls,
                                    order_id,
                                    parent_file_id,  # 原始压缩包的ID
                                    source_hash=source_id,
                                    from_zip=True,
                                    zip_path=file_path
                                )
                                current_app.logger.info(f"成功保存 {len(saved_files)} 个转换后的文件记录")
                                converted_files.extend(saved_files)
                            # 如果是内部压缩包，保存转换结果到数据库（如果有order_id）或暂存结果
                            elif depth > 0:
                                # 如果内部压缩包处理时也有order_id，直接保存到数据库
                                if order_id is not None:
                                    saved_files = FileService.save_converted_files_from_urls(
                                        converted_urls,
                                        order_id,
                                        parent_file_id,  # 可能为None
                                        source_hash=source_id,
                                        from_zip=True,
                                        zip_path=file_path
                                    )
                                    current_app.logger.info(f"内部压缩包文件 {filename} 成功保存 {len(saved_files)} 个转换后的文件记录")
                                    converted_files.extend(saved_files)
                                else:
                                    # 如果没有order_id，则创建临时对象（老行为，理论上不应该发生）
                                    current_app.logger.warning(f"内部压缩包文件 {filename} 没有order_id，只能暂存结果")
                                    for url in converted_urls:
                                        # 创建临时对象以便于外部处理
                                        temp_file = {
                                            'filename': os.path.basename(url),
                                            'file_path': url,
                                            'source_hash': source_id,
                                            'parent_hash': zip_hash,
                                            'from_nested_zip': True,
                                            'nested_level': depth,
                                            'original_filename': filename,
                                            'original_path': inner_file_path
                                        }
                                        converted_files.append(temp_file)
                        else:
                            current_app.logger.error(f"文件 {filename} 转换失败，未生成任何URL")
                    else:
                        current_app.logger.info(f"跳过不支持的文件类型: {filename} ({file_type})")
                
            return converted_files
                
        finally:
            # 清理临时提取目录
            if extract_dir and os.path.exists(extract_dir):
                try:
                    shutil.rmtree(extract_dir)
                    current_app.logger.info(f"已清理临时提取目录: {extract_dir}")
                except Exception as e:
                    current_app.logger.error(f"清理临时提取目录时出错: {str(e)}")

    @staticmethod
    def archive_file(file_path, category="general", description=None, tags=None):
        """将文件归档到归档服务
        
        Args:
            file_path: 文件路径
            category: 文件分类
            description: 文件描述
            tags: 文件标签列表
            
        Returns:
            归档成功返回归档文件信息字典，否则返回None
        """
        # 调用归档服务
        return ArchiveService.archive_file(file_path, category, description, tags)

    @staticmethod
    def get_file_by_hash(file_hash):
        """根据文件哈希值从归档服务获取文件信息
        
        Args:
            file_hash: 文件哈希值
            
        Returns:
            文件信息字典，如果未找到则返回None
        """
        return ArchiveService.get_file_by_hash(file_hash)

    @staticmethod
    def download_archived_file(file_id, target_path=None):
        """从归档服务下载文件
        
        Args:
            file_id: 归档文件ID
            target_path: 目标保存路径，如果为None则使用临时目录
            
        Returns:
            下载成功返回文件路径，否则返回None
        """
        return ArchiveService.download_file(file_id, target_path)

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
    @log_exceptions("转换文件时出错", default_return=[])
    def convert_to_images(file_path, output_dir=None, file_type="pdf", page_start=None, page_end=None, source_hash=None, order_id=None, parent_id=None):
        """转换文件为图像
        
        Args:
            file_path: 文件路径
            output_dir: 输出目录
            file_type: 文件类型
            page_start: 起始页码
            page_end: 结束页码
            source_hash: 源文件哈希值
            order_id: 订单ID
            parent_id: 父文件ID（如压缩包）
            
        Returns:
            转换后的文件URL列表
        """
        # 准备详细的调试日志
        current_app.logger.info(
            f"开始转换文件: path={file_path}, type={file_type}, "
            f"source_hash={source_hash}, order_id={order_id}, parent_id={parent_id}"
        )
        
        # 获取转换客户端
        from src.utils.convert_client import ConvertClient
        convert_client = ConvertClient(current_app.config.get('CONVERT_API'))
        
        # 检查健康状态
        if not convert_client.health_check():
            current_app.logger.error("转换服务不可用")
            flash("转换服务不可用", "danger")
            return []
            
        # 确保源文件哈希值有效 
        if not source_hash:
            source_hash = FileService.calculate_file_hash(file_path)[:6]
            current_app.logger.info(f"生成源文件哈希: {source_hash}")
        
        # 重要：使用订单号而不是订单ID
        order_dir_name = None
        if order_id is not None:
            # 获取订单号
            from src.services.order_service import OrderService
            order = OrderService.get_order(int(order_id))
            if order:
                order_dir_name = order.order_number
                current_app.logger.info(f"使用订单号作为目录: {order_dir_name}")
            else:
                # 如果找不到订单，使用ID作为备用
                order_dir_name = str(order_id)
                current_app.logger.warning(f"找不到订单ID {order_id}，使用ID作为目录")
        
        # 准备调用参数
        kwargs = {
            'output_dir': output_dir,
            'order_id': order_dir_name,
            'source_id': source_hash,
            'parent_id': parent_id
        }
        
        # 如果是PDF、PPT或Doc文档类型，添加DPI参数
        if file_type in ['pdf', 'docx', 'pptx']:
            kwargs['dpi'] = current_app.config.get('CONVERT_DPI', 150)
            
        # 从策略表中获取转换函数
        converter = FILE_TYPE_MAP.get(file_type, {}).get('converter')
        if not converter:
            current_app.logger.error(f"不支持的文件类型: {file_type}")
            return []
            
        # 调用适当的转换方法
        urls = converter(convert_client, file_path, **kwargs)
        
        # 处理单个URL的情况(图片转换)
        if isinstance(urls, str):
            urls = [urls]
            
        # 检查转换结果
        if not urls:
            current_app.logger.error(f"转换失败，没有返回任何URL: {file_path}")
            return []
        
        # 记录转换结果
        current_app.logger.info(f"文件转换成功: {file_path} -> {len(urls)} 个文件")
        return urls 