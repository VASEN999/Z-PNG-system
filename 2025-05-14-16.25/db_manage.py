#!/usr/bin/env python3
"""
数据库管理工具 - 集成了数据库重置、创建表和管理功能
"""
import os
import sys
import argparse
from app import create_app
from config import config
from models import db, AdminUser

def reset_db(app):
    """重置数据库"""
    db_path = os.path.join(os.path.dirname(__file__), 'app.db')
    if os.path.exists(db_path):
        print(f"删除数据库文件: {db_path}")
        os.remove(db_path)
    
    with app.app_context():
        print("创建新的数据库结构...")
        db.create_all()
        AdminUser.create_default_admin()
        print("数据库初始化完成")

def create_tables(app):
    """只创建表，不重置数据库"""
    with app.app_context():
        print("创建数据库表...")
        db.create_all()
        print("表创建完成")

def reset_admin(app):
    """重置管理员账户"""
    with app.app_context():
        print("重置管理员账户...")
        AdminUser.create_default_admin()
        print("管理员账户重置完成")

def main():
    parser = argparse.ArgumentParser(description='数据库管理工具')
    parser.add_argument('action', choices=['reset', 'create_tables', 'reset_admin'],
                        help='执行的操作: reset=重置数据库, create_tables=创建表, reset_admin=重置管理员')
    
    args = parser.parse_args()
    
    # 创建应用实例
    app = create_app(config['development'])
    
    if args.action == 'reset':
        reset_db(app)
    elif args.action == 'create_tables':
        create_tables(app)
    elif args.action == 'reset_admin':
        reset_admin(app)

if __name__ == '__main__':
    main()
