#!/usr/bin/env python3
import os
import sys
import logging
import platform
from socket import socket, AF_INET, SOCK_STREAM
import shutil
from datetime import datetime
from src.app import create_app
from src.models import db, AdminUser
import src.settings as config
import socket

# 设置环境变量连接到正确的微服务端口
# 从环境变量获取，如果环境变量没有设置，则使用默认值
os.environ.setdefault('CONVERT_SVC_URL', 'http://localhost:8081/api')
os.environ.setdefault('ARCHIVE_SVC_URL', 'http://localhost:8088/api/v1/archive')

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("root")

# 检测操作系统
os_name = platform.system()
logger.info(f"检测到操作系统: {os_name}")

# 获取当前环境
env = os.environ.get("FLASK_ENV", "development")
logger.info(f"运行环境: {env}")

# 创建应用实例
try:
    app = create_app()
    logger.info("应用实例创建成功")
except Exception as e:
    logger.error(f"应用创建失败: {str(e)}")
    sys.exit(1)

# 确保必要的目录存在
def ensure_directories_exist():
    try:
        for dir_path in [
            config.UPLOAD_FOLDER,
            config.CONVERTED_FOLDER,
            config.ARCHIVE_FOLDER,
            os.path.join(os.path.dirname(__file__), 'flask_session')
        ]:
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"目录已创建或已存在: {dir_path}")
    except Exception as e:
        logger.error(f"目录创建失败: {str(e)}")
        sys.exit(1)

# 检查端口是否可用
def is_port_available(port, host='127.0.0.1'):
    """检查指定端口是否可用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except:
        return False

# 查找可用端口
def find_available_port(start_port=8000):
    """从指定端口开始查找可用端口"""
    port = start_port
    while not is_port_available(port) and port < start_port + 100:
        port += 1
    return port

if __name__ == '__main__':
    try:
        # 确保目录存在
        ensure_directories_exist()
        
        # 获取数据库路径
        db_path = config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
        
        # 检查是否需要重置数据库
        reset_db = os.environ.get('RESET_DB', 'false').lower() == 'true'
        
        if reset_db and os.path.exists(db_path) and db_path != ':memory:':
            logger.info(f"删除数据库文件: {db_path}")
            os.remove(db_path)
        
        # 创建新的数据库及表
        with app.app_context():
            logger.info("创建新的数据库结构...")
            db.create_all()
            # 使用配置中的默认管理员信息
            default_admin = AdminUser.query.filter_by(username=config.ADMIN_USERNAME).first()
            if not default_admin:
                default_admin = AdminUser(
                    username=config.ADMIN_USERNAME,
                    is_admin=True,
                    full_name='系统管理员',
                    email=config.ADMIN_EMAIL
                )
                default_admin.set_password(config.ADMIN_PASSWORD)
                db.session.add(default_admin)
                db.session.commit()
                logger.info(f"创建默认管理员: {config.ADMIN_USERNAME}")
            logger.info("数据库初始化完成")
        
        # 启动Flask应用
        # 使用0.0.0.0允许局域网访问
        host = '0.0.0.0'
        
        # 尝试使用用户指定的端口，如果不可用则自动查找可用端口
        preferred_port = int(os.environ.get('PORT', 8080))
        if not is_port_available(preferred_port, host):
            logger.warning(f"端口 {preferred_port} 已被占用，正在查找可用端口...")
            port = find_available_port(8000)
            logger.info(f"自动选择端口 {port}")
        else:
            port = preferred_port
            
        debug = config.DEBUG
        
        logger.info(f"应用启动于 http://{host}:{port}，debug={debug}")
        print(f"应用已启动，请访问: http://{host}:{port}")
        
        # 使用threaded=True提高并发性能
        app.run(host=host, port=port, debug=debug, threaded=True)
    except Exception as e:
        logger.error(f"应用启动失败: {str(e)}")
        sys.exit(1) 