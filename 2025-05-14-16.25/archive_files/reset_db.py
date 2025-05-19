#!/usr/bin/env python
import os
import sqlite3
import logging
import sys
import inspect
from datetime import datetime
from app import create_app
from config import config
from models import db, AdminUser, Order, UploadedFile, ConvertedFile

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def reset_database():
    """
    完全重置数据库：
    1. 删除现有数据库文件
    2. 创建新的数据库和表结构
    3. 添加默认管理员账户
    4. 验证表结构是否正确
    """
    app = create_app(config['development'])
    
    with app.app_context():
        # 1. 删除现有数据库文件
        db_path = os.path.join(os.path.dirname(__file__), 'app.db')
        if os.path.exists(db_path):
            logger.info(f"删除现有数据库文件: {db_path}")
            os.remove(db_path)
        
        # 打印模型信息
        logger.info(f"Order模型表名: {Order.__tablename__ if hasattr(Order, '__tablename__') else 'order'}")
        logger.info(f"AdminUser模型表名: {AdminUser.__tablename__ if hasattr(AdminUser, '__tablename__') else 'admin_user'}")
        logger.info(f"UploadedFile模型表名: {UploadedFile.__tablename__ if hasattr(UploadedFile, '__tablename__') else 'uploaded_file'}")
        logger.info(f"ConvertedFile模型表名: {ConvertedFile.__tablename__ if hasattr(ConvertedFile, '__tablename__') else 'converted_file'}")
        
        # 打印所有模型的表名
        from models import db
        for name, obj in inspect.getmembers(sys.modules['models']):
            if inspect.isclass(obj) and hasattr(obj, '__tablename__'):
                logger.info(f"发现模型类: {name}, 表名: {obj.__tablename__}")
        
        # 2. 创建新的数据库和表结构
        logger.info("创建新的数据库和表结构...")
        db.create_all()
        
        # 3. 添加默认管理员账户
        logger.info("创建默认管理员账户...")
        admin = AdminUser(
            username='admin', 
            is_admin=True,
            full_name='系统管理员',
            email='admin@example.com',
            is_active=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        
        # 4. 验证表结构是否正确
        logger.info("验证表结构...")
        
        # 连接到SQLite数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 列出所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        logger.info(f"数据库中的所有表: {table_names}")
        
        # 检查所有预期的表是否存在
        expected_tables = ['orders', 'admin_user', 'uploaded_files', 'converted_files']
        missing_tables = [table for table in expected_tables if table not in table_names]
        
        if missing_tables:
            logger.error(f"缺少以下表: {missing_tables}")
            conn.close()
            return
        else:
            logger.info("所有预期的表都已创建")
        
        # 验证订单表中是否有 status 字段
        cursor.execute("PRAGMA table_info('orders')")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"orders表的列: {column_names}")
        
        # 验证admin_user表是否有正确的列
        cursor.execute("PRAGMA table_info('admin_user')")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"admin_user表的列: {column_names}")
        
        # 验证 uploaded_files 表是否有正确的列
        cursor.execute("PRAGMA table_info('uploaded_files')")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"uploaded_files表的列: {column_names}")
        
        # 验证 converted_files 表是否有正确的列
        cursor.execute("PRAGMA table_info('converted_files')")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        logger.info(f"converted_files表的列: {column_names}")
        
        # 关闭数据库连接
        conn.close()
        
        logger.info("数据库重置完成!")

if __name__ == "__main__":
    reset_database() 