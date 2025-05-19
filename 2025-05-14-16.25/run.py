from app import create_app
from config import config
from models import db, AdminUser
import os
import logging
import sys
import platform
import socket

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()  # 同时输出到控制台
    ]
)

# 获取当前操作系统
current_os = platform.system()
logging.info(f"检测到操作系统: {current_os}")

# 创建应用实例
try:
    app = create_app(config['development'])
    logging.info("应用实例创建成功")
except Exception as e:
    logging.error(f"应用创建失败: {str(e)}")
    sys.exit(1)

# 确保必要的目录存在
def ensure_directories_exist():
    try:
        for dir_path in [
            os.path.join(os.path.dirname(__file__), 'app', 'uploads'),
            os.path.join(os.path.dirname(__file__), 'app', 'converted'),
            os.path.join(os.path.dirname(__file__), 'app', 'archive'),
            os.path.join(os.path.dirname(__file__), 'flask_session')
        ]:
            os.makedirs(dir_path, exist_ok=True)
            logging.info(f"目录已创建或已存在: {dir_path}")
    except Exception as e:
        logging.error(f"目录创建失败: {str(e)}")
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
        db_path = os.path.join(os.path.dirname(__file__), 'app.db')
        
        # 检查是否需要重置数据库
        reset_db = os.environ.get('RESET_DB', 'false').lower() == 'true'
        
        if reset_db and os.path.exists(db_path):
            logging.info(f"删除数据库文件: {db_path}")
            os.remove(db_path)
        
        # 创建新的数据库及表
        with app.app_context():
            logging.info("创建新的数据库结构...")
            db.create_all()
            AdminUser.create_default_admin()
            logging.info("数据库初始化完成")
        
        # 启动Flask应用
        # 明确使用localhost而非0.0.0.0，避免网络问题
        host = '127.0.0.1'
        
        # 尝试使用用户指定的端口，如果不可用则自动查找可用端口
        preferred_port = int(os.environ.get('PORT', 8080))
        if not is_port_available(preferred_port, host):
            logging.warning(f"端口 {preferred_port} 已被占用，正在查找可用端口...")
            port = find_available_port(8000)
            logging.info(f"自动选择端口 {port}")
        else:
            port = preferred_port
            
        debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
        
        logging.info(f"应用启动于 http://{host}:{port}，debug={debug}")
        print(f"应用已启动，请访问: http://{host}:{port}")
        
        # 使用threaded=True提高并发性能
        app.run(host=host, port=port, debug=debug, threaded=True)
    except Exception as e:
        logging.error(f"应用启动失败: {str(e)}")
        sys.exit(1) 