#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库表创建脚本

用于创建程序所需的全部数据库表，并添加默认管理员账户
"""

import os
import logging
from datetime import datetime
from flask import Flask
from models import db, AdminUser, Order, UploadedFile, ConvertedFile, Email, EmailAttachment
from config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("create_tables.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建Flask应用实例
app = Flask(__name__)

# 配置数据库
app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db.init_app(app)

def create_tables():
    """创建所有数据库表"""
    with app.app_context():
        # 检查数据库文件是否存在
        db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')
        if os.path.exists(db_file):
            logger.warning(f"数据库文件 {db_file} 已存在，将会创建表（如果不存在）")
        
        try:
            logger.info("开始创建数据库表...")
            
            # 创建所有表
            db.create_all()
            
            # 创建默认管理员用户
            default_admin = AdminUser.query.filter_by(username='admin').first()
            if not default_admin:
                logger.info("创建默认管理员用户")
                default_admin = AdminUser(
                    username='admin', 
                    is_admin=True,
                    full_name='系统管理员',
                    email='admin@example.com'
                )
                default_admin.set_password('admin123')
                db.session.add(default_admin)
                db.session.commit()
                logger.info("默认管理员用户创建成功")
            else:
                logger.info("默认管理员用户已存在")
                
            # 创建测试数据（如果需要）
            if os.environ.get('CREATE_TEST_DATA') == 'true':
                create_test_data()
            
            logger.info("数据库表创建完成")
            
            # 列出所有已创建的表
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"数据库中的表：{', '.join(tables)}")
            
            # 显示表中的记录数
            logger.info(f"AdminUser表中有 {AdminUser.query.count()} 条记录")
            logger.info(f"Order表中有 {Order.query.count()} 条记录")
            logger.info(f"UploadedFile表中有 {UploadedFile.query.count()} 条记录")
            logger.info(f"ConvertedFile表中有 {ConvertedFile.query.count()} 条记录")
            logger.info(f"Email表中有 {Email.query.count()} 条记录")
            logger.info(f"EmailAttachment表中有 {EmailAttachment.query.count()} 条记录")
            
        except Exception as e:
            logger.error(f"创建表时出错: {str(e)}")
            raise

def create_test_data():
    """创建测试数据"""
    logger.info("创建测试数据...")
    
    # 创建测试用户
    test_user = AdminUser.query.filter_by(username='test').first()
    if not test_user:
        test_user = AdminUser(
            username='test',
            is_admin=False,
            full_name='测试用户',
            email='test@example.com'
        )
        test_user.set_password('test123')
        db.session.add(test_user)
        db.session.commit()
        logger.info("测试用户创建成功")
    
    # 创建测试订单
    test_order = Order.query.filter_by(order_number='TEST-ORDER-001').first()
    if not test_order:
        test_order = Order(
            order_number='TEST-ORDER-001',
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True,
            status=Order.STATUS_ACTIVE,
            note='测试订单',
            user_id=test_user.id if test_user else None
        )
        db.session.add(test_order)
        db.session.commit()
        logger.info("测试订单创建成功")
    
    # 创建测试邮件
    test_email = Email.query.filter_by(subject='测试邮件').first()
    if not test_email:
        test_email = Email(
            uid='test_uid_123',
            subject='测试邮件',
            sender='sender@example.com',
            sender_name='测试发件人',
            received_at=datetime.now(),
            content='这是一封测试邮件的内容',
            processed=False
        )
        db.session.add(test_email)
        db.session.commit()
        logger.info("测试邮件创建成功")
        
        # 创建测试邮件附件
        test_attachment = EmailAttachment(
            filename='test.txt',
            saved_as='20250101000000_test.txt',
            file_path='app/uploads/email_1/20250101000000_test.txt',
            file_size=1024,
            file_type='txt',
            file_hash='0123456789abcdef0123456789abcdef',
            email_id=test_email.id
        )
        db.session.add(test_attachment)
        db.session.commit()
        logger.info("测试邮件附件创建成功")

if __name__ == '__main__':
    create_tables() 