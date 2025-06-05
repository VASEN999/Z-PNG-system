import os
import hashlib
import tempfile
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import docx
from pptx import Presentation

def create_info_image(filename, message, output_dir=None):
    """创建一个包含信息的图片
    
    Args:
        filename: 输出文件名
        message: 要显示的信息
        output_dir: 输出目录，如果为None则使用当前目录
        
    Returns:
        生成的图片路径
    """
    # 设置图片尺寸和背景色
    width, height = 800, 600
    background_color = (255, 255, 255)
    text_color = (0, 0, 0)
    
    # 创建图片
    image = Image.new('RGB', (width, height), background_color)
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype("simhei.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("Arial.ttf", 24)
        except:
            font = ImageFont.load_default()
    
    # 绘制文本
    # 处理多行文本
    lines = message.split('\n')
    y = 100
    for line in lines:
        # 计算文本宽度以居中显示
        text_width, text_height = draw.textsize(line, font=font)
        x = (width - text_width) / 2
        draw.text((x, y), line, fill=text_color, font=font)
        y += text_height + 10
    
    # 保存图片
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
    else:
        output_path = filename
    
    image.save(output_path)
    return output_path

def convert_pdf_to_png(pdf_path, output_dir=None, dpi=300):
    """将PDF文件转换为PNG图片
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录，如果为None则使用临时目录
        dpi: 输出图片的DPI
        
    Returns:
        生成的PNG文件路径列表
    """
    # 如果没有指定输出目录，则创建临时目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # 打开PDF文件
    pdf_document = fitz.open(pdf_path)
    
    output_files = []
    
    # 遍历每一页
    for page_num in range(len(pdf_document)):
        # 获取页面
        page = pdf_document.load_page(page_num)
        
        # 将页面渲染为图片
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        
        # 生成输出文件名
        output_filename = f"{base_name}_page{page_num+1}.png"
        output_path = os.path.join(output_dir, output_filename)
        
        # 保存图片
        pix.save(output_path)
        
        output_files.append(output_path)
    
    # 关闭PDF文件
    pdf_document.close()
    
    return output_files

def convert_docx_to_png(docx_path, output_dir=None, dpi=300):
    """将DOCX文件转换为PNG图片
    
    Args:
        docx_path: DOCX文件路径
        output_dir: 输出目录，如果为None则使用临时目录
        dpi: 输出图片的DPI
        
    Returns:
        生成的PNG文件路径列表
    """
    # 如果没有指定输出目录，则创建临时目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(docx_path))[0]
    
    # 创建临时PDF文件
    temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    temp_pdf_path = temp_pdf.name
    temp_pdf.close()
    
    # 使用外部工具（如libreoffice）将DOCX转换为PDF
    # 这里需要根据实际环境配置相应的转换命令
    try:
        import subprocess
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', 
                       '--outdir', os.path.dirname(temp_pdf_path), docx_path], 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 如果转换成功，使用convert_pdf_to_png函数将PDF转换为PNG
        if os.path.exists(temp_pdf_path):
            output_files = convert_pdf_to_png(temp_pdf_path, output_dir, dpi)
            
            # 删除临时PDF文件
            os.unlink(temp_pdf_path)
            
            return output_files
    except:
        # 如果转换失败，创建一个错误信息图片
        error_message = f"无法转换文件: {os.path.basename(docx_path)}\n请确保已安装LibreOffice"
        error_image_path = create_info_image(f"{base_name}_error.png", error_message, output_dir)
        return [error_image_path]
    
    # 如果上述方法失败，返回一个错误信息图片
    error_message = f"无法转换文件: {os.path.basename(docx_path)}"
    error_image_path = create_info_image(f"{base_name}_error.png", error_message, output_dir)
    return [error_image_path]

def convert_pptx_to_png(pptx_path, output_dir=None, dpi=300):
    """将PPTX文件转换为PNG图片
    
    Args:
        pptx_path: PPTX文件路径
        output_dir: 输出目录，如果为None则使用临时目录
        dpi: 输出图片的DPI
        
    Returns:
        生成的PNG文件路径列表
    """
    # 如果没有指定输出目录，则创建临时目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(pptx_path))[0]
    
    # 创建临时PDF文件
    temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    temp_pdf_path = temp_pdf.name
    temp_pdf.close()
    
    # 使用外部工具（如libreoffice）将PPTX转换为PDF
    # 这里需要根据实际环境配置相应的转换命令
    try:
        import subprocess
        subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf', 
                       '--outdir', os.path.dirname(temp_pdf_path), pptx_path], 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 如果转换成功，使用convert_pdf_to_png函数将PDF转换为PNG
        if os.path.exists(temp_pdf_path):
            output_files = convert_pdf_to_png(temp_pdf_path, output_dir, dpi)
            
            # 删除临时PDF文件
            os.unlink(temp_pdf_path)
            
            return output_files
    except:
        # 如果转换失败，创建一个错误信息图片
        error_message = f"无法转换文件: {os.path.basename(pptx_path)}\n请确保已安装LibreOffice"
        error_image_path = create_info_image(f"{base_name}_error.png", error_message, output_dir)
        return [error_image_path]
    
    # 如果上述方法失败，返回一个错误信息图片
    error_message = f"无法转换文件: {os.path.basename(pptx_path)}"
    error_image_path = create_info_image(f"{base_name}_error.png", error_message, output_dir)
    return [error_image_path]

def convert_image_to_png(image_path, output_dir=None):
    """将图片文件转换为PNG格式
    
    Args:
        image_path: 图片文件路径
        output_dir: 输出目录，如果为None则使用临时目录
        
    Returns:
        生成的PNG文件路径
    """
    # 如果没有指定输出目录，则创建临时目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp()
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    # 获取文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    
    # 生成输出文件名
    output_filename = f"{base_name}.png"
    output_path = os.path.join(output_dir, output_filename)
    
    try:
        # 打开图片
        img = Image.open(image_path)
        
        # 如果图片不是PNG格式，转换为PNG格式
        if img.format != 'PNG':
            # 如果图片有透明通道，保留透明通道
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')
        
        # 保存为PNG
        img.save(output_path, 'PNG')
        
        return output_path
    except Exception as e:
        # 如果转换失败，创建一个错误信息图片
        error_message = f"无法转换图片: {os.path.basename(image_path)}\n错误: {str(e)}"
        error_image_path = create_info_image(f"{base_name}_error.png", error_message, output_dir)
        return error_image_path 