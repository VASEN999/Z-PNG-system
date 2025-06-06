import os
import requests
import logging
from flask import current_app

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
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            return response.status_code == 200 and response.json().get('status') == 'ok'
        except Exception as e:
            logger.error(f"连接转换服务失败: {str(e)}")
            return False
    
    def convert_pdf_to_png(self, pdf_path, output_dir=None, dpi=None):
        """将PDF文件转换为PNG图片
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            
        Returns:
            转换成功返回生成的PNG文件路径列表，失败返回None
        """
        payload = {
            "file_path": pdf_path
        }
        
        if output_dir:
            payload["output_dir"] = output_dir
            
        if dpi:
            payload["dpi"] = dpi
        
        try:
            response = requests.post(f"{self.base_url}/api/convert", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if result["success"]:
                    return result["files"]
                else:
                    logger.error(f"转换PDF失败: {result.get('error')}")
            else:
                logger.error(f"转换服务返回错误: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"调用转换服务失败: {str(e)}")
        
        return None
    
    def convert_docx_to_png(self, docx_path, output_dir=None, dpi=None):
        """将Word文档转换为PNG图片
        
        Args:
            docx_path: Word文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            
        Returns:
            转换成功返回生成的PNG文件路径列表，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        return self.convert_pdf_to_png(docx_path, output_dir, dpi)
    
    def convert_pptx_to_png(self, pptx_path, output_dir=None, dpi=None):
        """将PPT文档转换为PNG图片
        
        Args:
            pptx_path: PPT文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            dpi: 输出图片的DPI，如果为None则使用服务默认值
            
        Returns:
            转换成功返回生成的PNG文件路径列表，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        return self.convert_pdf_to_png(pptx_path, output_dir, dpi)
    
    def convert_image_to_png(self, image_path, output_dir=None):
        """将图片转换为PNG格式
        
        Args:
            image_path: 图片文件路径
            output_dir: 输出目录，如果为None则使用服务默认目录
            
        Returns:
            转换成功返回生成的PNG文件路径，失败返回None
        """
        # 与PDF转换使用相同的API，服务会根据文件扩展名判断类型
        result = self.convert_pdf_to_png(image_path, output_dir)
        if result and len(result) > 0:
            return result[0]  # 图片转换只会返回一个文件
        return None
    
    def batch_convert(self, files):
        """批量转换文件
        
        Args:
            files: 文件配置列表，每个配置包含以下字段:
                  - file_path: 文件路径(必须)
                  - output_dir: 输出目录(可选)
                  - dpi: 输出DPI(可选)
            
        Returns:
            转换结果字典，键为文件路径，值为转换结果
        """
        payload = {
            "files": files
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/convert-batch", json=payload, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result.get("results", {})
            else:
                logger.error(f"批量转换服务返回错误: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"调用批量转换服务失败: {str(e)}")
        
        return {}

# 创建默认客户端实例
convert_client = ConvertClient() 