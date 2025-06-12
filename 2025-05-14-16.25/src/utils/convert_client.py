import os
import requests
import json
from flask import current_app, flash
import logging
import urllib.parse
import hashlib

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConvertClient:
    """文件转换服务客户端"""
    
    def __init__(self, base_url=None):
        """初始化客户端
        
        Args:
            base_url: 转换服务的基础URL，如果为None则从环境变量或配置获取
        """
        self.base_url = base_url or os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081')
    
    def health_check(self):
        """检查转换服务是否正常运行
        
        Returns:
            服务正常运行返回True，否则返回False
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200 and response.json().get('status') == 'ok'
        except Exception as e:
            logger.error(f"连接转换服务失败: {str(e)}")
            return False
    
    def generate_source_id(self, file_path, parent_id=None):
        """生成源文件标识符
        
        Args:
            file_path: 文件路径
            parent_id: 父文件标识符（用于嵌套文件）
            
        Returns:
            源文件标识符
        """
        hasher = hashlib.sha256()
        
        # 添加文件路径
        hasher.update(file_path.encode('utf-8'))
        
        # 添加父ID（如果有）
        if parent_id:
            hasher.update(parent_id.encode('utf-8'))
        
        # 生成哈希并截取前6位
        hash_hex = hasher.hexdigest()
        return hash_hex[:6]
    
    def convert_pdf_to_png(self, pdf_path, output_dir=None, dpi=None, order_id=None, source_id=None, parent_id=None):
        """将PDF文件转换为PNG图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            order_id: 订单ID，用于按订单组织文件存储
            source_id: 源文件唯一标识符
            parent_id: 父文件标识符（用于嵌套文件）
            
        Returns:
            转换成功返回生成的PNG文件URL列表，失败返回None
        """
        payload = {
            "file_path": pdf_path
        }
        
        if output_dir:
            payload["output_dir"] = output_dir
            
        if dpi:
            payload["dpi"] = dpi
            
        # 确保order_id是字符串类型
        if order_id is not None:
            payload["order_id"] = str(order_id)
            logger.info(f"传递订单ID: {order_id}（字符串类型）")
        
        # 添加源文件标识符
        if source_id:
            payload["source_id"] = source_id
        
        # 添加父文件标识符
        if parent_id:
            payload["parent_id"] = parent_id
        
        try:
            # 记录请求负载
            logger.info(f"发送转换请求: {payload}")
            
            response = requests.post(f"{self.base_url}/api/convert", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    # 将物理路径转换为URL
                    file_urls = [self.get_file_url(file_path) for file_path in result["files"]]
                    return file_urls
                else:
                    logger.error(f"转换PDF失败: {result.get('error')}")
            else:
                logger.error(f"转换服务返回错误: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"调用转换服务失败: {str(e)}")
        
        return None
    
    def convert_docx_to_png(self, docx_path, output_dir=None, dpi=None, order_id=None, source_id=None, parent_id=None):
        """将Word文档转换为PNG图片
        
        Args:
            docx_path: Word文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            order_id: 订单ID，用于按订单组织文件存储
            source_id: 源文件唯一标识符
            parent_id: 父文件标识符（用于嵌套文件）
            
        Returns:
            转换成功返回生成的PNG文件URL列表，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        return self.convert_pdf_to_png(docx_path, output_dir, dpi, order_id, source_id, parent_id)
    
    def convert_pptx_to_png(self, pptx_path, output_dir=None, dpi=None, order_id=None, source_id=None, parent_id=None):
        """将PPT文档转换为PNG图片
        
        Args:
            pptx_path: PPT文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            order_id: 订单ID，用于按订单组织文件存储
            source_id: 源文件唯一标识符
            parent_id: 父文件标识符（用于嵌套文件）
            
        Returns:
            转换成功返回生成的PNG文件URL列表，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        return self.convert_pdf_to_png(pptx_path, output_dir, dpi, order_id, source_id, parent_id)
    
    def convert_image_to_png(self, image_path, output_dir=None, order_id=None, source_id=None, parent_id=None):
        """将图片转换为PNG格式
        
        Args:
            image_path: 图片文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            order_id: 订单ID，用于按订单组织文件存储
            source_id: 源文件唯一标识符
            parent_id: 父文件标识符（用于嵌套文件）
            
        Returns:
            转换成功返回生成的PNG文件URL，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        result = self.convert_pdf_to_png(image_path, output_dir, None, order_id, source_id, parent_id)
        if result and len(result) > 0:
            return result[0]  # 图片转换只会返回一个文件
        return None
    
    def batch_convert(self, files, order_id=None):
        """批量转换文件
        
        Args:
            files: 文件配置列表，每个配置包含以下字段:
                  - file_path: 文件路径(必须)
                  - output_dir: 输出目录(可选)
                  - dpi: 输出DPI(可选)
                  - source_id: 源文件标识符(可选)
                  - parent_id: 父文件标识符(可选)
            order_id: 批量转换关联的订单ID(可选)
            
        Returns:
            转换结果字典，键为文件路径，值为转换结果
        """
        # 确保文件列表中的order_id都是字符串类型
        for file_config in files:
            if 'order_id' in file_config and file_config['order_id'] is not None:
                file_config['order_id'] = str(file_config['order_id'])
                
        payload = {
            "files": files
        }
        
        # 确保全局order_id是字符串类型
        if order_id is not None:
            payload["order_id"] = str(order_id)
            logger.info(f"批量转换使用订单ID: {order_id}（字符串类型）")
        
        try:
            # 记录请求负载
            logger.info(f"发送批量转换请求，包含 {len(files)} 个文件")
            
            response = requests.post(f"{self.base_url}/api/convert-batch", json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                
                # 处理结果，将物理路径转换为URL
                processed_results = {}
                for file_path, file_result in result.get("results", {}).items():
                    if file_result.get("success") and "files" in file_result:
                        file_result["files"] = [self.get_file_url(f) for f in file_result["files"]]
                    processed_results[file_path] = file_result
                
                return processed_results
            else:
                logger.error(f"批量转换服务返回错误: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"调用批量转换服务失败: {str(e)}")
        
        return {}
    
    def get_file_url(self, file_path):
        """将物理文件路径转换为可访问的URL
        
        Args:
            file_path: 文件的物理路径
            
        Returns:
            可通过HTTP访问的文件URL
        """
        try:
            # 获取转换服务地址
            convert_api = self.base_url
            
            # 标准化路径分隔符，确保在Windows和Unix上都能正常工作
            norm_path = file_path.replace("\\", "/")
            
            # 详细记录处理过程
            logger.info(f"处理文件路径: {file_path}，标准化后: {norm_path}")
            
            # 默认使用文件名作为路径
            file_name = os.path.basename(norm_path)
            relative_path = file_name
            
            # 如果路径中包含'converted'，提取相对路径
            if '/converted/' in norm_path:
                parts = norm_path.split('/converted/')
                if len(parts) > 1:
                    relative_path = parts[1]
                    logger.info(f"从路径中提取相对部分: {relative_path}")
            
            # 构建URL
            file_url = f"{convert_api}/files/{relative_path}"
            
            # 记录生成的URL和相对路径
            logger.info(f"转换文件路径: {file_path} -> URL: {file_url}, 相对路径: {relative_path}")
            
            return file_url
        except Exception as e:
            logger.error(f"生成文件URL出错: {str(e)}")
            return ""
    
    def get_file_info(self, file_path):
        """获取转换后文件的信息
        
        Args:
            file_path: 文件的物理路径或URL
            
        Returns:
            包含文件URL和其他元数据的字典
        """
        # 如果输入是URL，直接返回
        if file_path.startswith('http'):
            return {
                "url": file_path,
                "filename": os.path.basename(urllib.parse.unquote(file_path))
            }
        
        # 否则，将物理路径转换为URL
        filename = os.path.basename(file_path)
        file_url = self.get_file_url(file_path)
        
        return {
            "url": file_url,
            "filename": filename
        }

# 创建默认客户端实例
convert_client = ConvertClient() 