import os
import shutil
import logging
import hashlib
from datetime import datetime
from app import create_app
from config import config
from models import db, Order, UploadedFile, ConvertedFile

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def calculate_file_hash(file_path):
    """计算文件的SHA-256哈希值"""
    try:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # 读取文件块并更新哈希
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希值时出错: {str(e)}")
        return None

def rebuild_archives():
    """重建所有订单的文件存档"""
    app = create_app(config['development'])
    
    with app.app_context():
        logger.info("开始重建订单存档...")
        
        # 检查/创建存档目录
        uploads_archive_dir = os.path.join(app.config['ARCHIVE_FOLDER'], 'uploads')
        converted_archive_dir = os.path.join(app.config['ARCHIVE_FOLDER'], 'converted')
        os.makedirs(uploads_archive_dir, exist_ok=True)
        os.makedirs(converted_archive_dir, exist_ok=True)
        
        # 获取所有订单
        orders = Order.query.all()
        logger.info(f"找到 {len(orders)} 个订单需要处理")
        
        # 扫描当前的uploads和converted文件夹
        current_uploads = set(os.listdir(app.config['UPLOAD_FOLDER']))
        current_converted = set(os.listdir(app.config['CONVERTED_FOLDER']))
        
        logger.info(f"当前上传目录中有 {len(current_uploads)} 个文件")
        logger.info(f"当前转换目录中有 {len(current_converted)} 个文件")
        
        # 计算并更新所有现有文件的哈希值
        update_hashes_for_existing_files(app)
        
        for order in orders:
            logger.info(f"处理订单 #{order.order_number}")
            
            # 为订单创建存档目录
            order_uploads_dir = os.path.join(uploads_archive_dir, order.order_number)
            order_converted_dir = os.path.join(converted_archive_dir, order.order_number)
            os.makedirs(order_uploads_dir, exist_ok=True)
            os.makedirs(order_converted_dir, exist_ok=True)
            
            # 处理上传文件
            for upload_file in order.files:
                filename = os.path.basename(upload_file.file_path)
                
                # 检查文件是否存在于当前上传目录
                if filename in current_uploads:
                    src_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    dst_path = os.path.join(order_uploads_dir, filename)
                    try:
                        shutil.copy2(src_path, dst_path)
                        # 更新数据库中的文件路径
                        upload_file.file_path = dst_path
                        
                        # 如果没有哈希值，计算并更新
                        if not upload_file.file_hash:
                            file_hash = calculate_file_hash(dst_path)
                            if file_hash:
                                upload_file.file_hash = file_hash
                                logger.info(f"更新上传文件哈希值: {filename} -> {file_hash[:8]}...")
                        
                        logger.info(f"已存档上传文件: {filename} -> {dst_path}")
                    except Exception as e:
                        logger.error(f"存档上传文件 {filename} 时出错: {e}")
                else:
                    logger.warning(f"上传文件 {filename} 不存在，无法存档")
            
            # 处理转换文件
            for converted_file in order.conversions:
                filename = os.path.basename(converted_file.file_path)
                
                # 检查文件是否存在于当前转换目录
                if filename in current_converted:
                    src_path = os.path.join(app.config['CONVERTED_FOLDER'], filename)
                    dst_path = os.path.join(order_converted_dir, filename)
                    try:
                        shutil.copy2(src_path, dst_path)
                        # 更新数据库中的文件路径
                        converted_file.file_path = dst_path
                        
                        # 尝试为转换文件关联源文件哈希
                        update_converted_file_source_hash(converted_file)
                        
                        logger.info(f"已存档转换文件: {filename} -> {dst_path}")
                    except Exception as e:
                        logger.error(f"存档转换文件 {filename} 时出错: {e}")
                else:
                    logger.warning(f"转换文件 {filename} 不存在，无法存档")
        
        # 重建哈希关系映射表，确保PNG能通过哈希值映射到原文件
        rebuild_hash_relationships()
        
        # 提交所有更改
        db.session.commit()
        logger.info("订单存档重建完成")

def update_hashes_for_existing_files(app):
    """为现有文件更新哈希值"""
    logger.info("开始更新文件哈希值...")
    
    # 更新上传文件的哈希值
    uploaded_files = UploadedFile.query.all()
    for upload_file in uploaded_files:
        if not upload_file.file_hash and os.path.exists(upload_file.file_path):
            file_hash = calculate_file_hash(upload_file.file_path)
            if file_hash:
                upload_file.file_hash = file_hash
                logger.info(f"更新上传文件哈希值: {os.path.basename(upload_file.file_path)} -> {file_hash[:8]}...")
    
    # 保存更改
    db.session.commit()
    logger.info("完成文件哈希值更新")

def update_converted_file_source_hash(converted_file):
    """更新转换文件的源文件哈希值"""
    # 如果已有源文件ID，使用源文件的哈希值
    if converted_file.source_file_id and not converted_file.source_hash:
        source_file = UploadedFile.query.get(converted_file.source_file_id)
        if source_file and source_file.file_hash:
            converted_file.source_hash = source_file.file_hash
            logger.info(f"从源文件更新转换文件哈希值: {os.path.basename(converted_file.file_path)} -> {source_file.file_hash[:8]}...")
    
    # 如果是从ZIP提取的文件，使用ZIP文件的哈希值
    elif converted_file.from_zip and converted_file.zip_path and not converted_file.source_hash:
        # 查找上传的ZIP文件
        zip_filename = os.path.basename(converted_file.zip_path)
        zip_file = UploadedFile.query.filter_by(filename=zip_filename).first()
        if zip_file and zip_file.file_hash:
            converted_file.source_hash = zip_file.file_hash
            logger.info(f"从ZIP更新转换文件哈希值: {os.path.basename(converted_file.file_path)} -> {zip_file.file_hash[:8]}...")

def rebuild_hash_relationships():
    """重建文件哈希关系，确保不同批次的相同内容文件可以互相映射"""
    logger.info("开始重建哈希关系...")
    
    # 创建哈希映射表
    hash_to_files = {}
    
    # 收集所有上传文件的哈希值
    for upload_file in UploadedFile.query.all():
        if upload_file.file_hash:
            if upload_file.file_hash not in hash_to_files:
                hash_to_files[upload_file.file_hash] = []
            hash_to_files[upload_file.file_hash].append(upload_file)
    
    # 对于每个转换文件，如果没有源哈希值但有源文件ID，尝试设置源哈希值
    updated = 0
    for converted_file in ConvertedFile.query.all():
        if not converted_file.source_hash and converted_file.source_file_id:
            source_file = UploadedFile.query.get(converted_file.source_file_id)
            if source_file and source_file.file_hash:
                converted_file.source_hash = source_file.file_hash
                updated += 1
    
    # 对于每个源哈希值，确保所有相关的转换文件都有关联
    for file_hash, files in hash_to_files.items():
        if len(files) > 1:
            logger.info(f"发现 {len(files)} 个具有相同哈希值的文件: {file_hash[:8]}...")
    
    logger.info(f"更新了 {updated} 个转换文件的源哈希值")

if __name__ == "__main__":
    rebuild_archives() 