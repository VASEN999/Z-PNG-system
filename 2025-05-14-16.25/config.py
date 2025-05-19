import os
import secrets

class Config:
    """基本配置类"""
    # 应用配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secure-and-stable-key-for-development'  # 固定密钥以避免每次重启变化
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    
    # 会话配置
    SESSION_TYPE = 'filesystem'  # 使用文件系统存储会话
    SESSION_PERMANENT = True  # 会话持久化
    PERMANENT_SESSION_LIFETIME = 86400  # 会话生存期为1天（秒）
    SESSION_USE_SIGNER = True  # 对cookie中的会话ID进行签名
    SESSION_COOKIE_SECURE = False  # 开发环境不需要HTTPS
    SESSION_COOKIE_HTTPONLY = True  # 防止JavaScript访问会话cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # 防止CSRF攻击
    SESSION_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_session')  # 会话文件存储位置
    
    # CSRF保护配置
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or 'csrf-key-for-development'  # 固定CSRF密钥
    WTF_CSRF_TIME_LIMIT = 3600  # CSRF令牌有效期（秒）
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'  # 使用简单的相对路径
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 文件存储配置
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'uploads')
    CONVERTED_FOLDER = os.path.join(BASE_DIR, 'app', 'converted')
    ARCHIVE_FOLDER = os.path.join(BASE_DIR, 'app', 'archive')  # 存储按订单号归档的文件
    ORDER_DATA_FILE = os.path.join(BASE_DIR, 'order_data.json')  # 订单数据备份
    
    # 邮箱配置
    MAIL_HOST = os.environ.get('MAIL_HOST') or 'imap.qiye.163.com'  # 邮箱服务器
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 993)  # 邮箱端口
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or ''  # 邮箱账号
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or ''  # 邮箱密码
    MAIL_FOLDER = os.environ.get('MAIL_FOLDER') or 'INBOX'  # 邮箱文件夹
    MAIL_CHECK_INTERVAL = int(os.environ.get('MAIL_CHECK_INTERVAL') or 300)  # 邮件检查间隔（秒）
    
    # 安全配置
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'  # 默认密码
    
    # 确保所需目录存在
    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.CONVERTED_FOLDER, exist_ok=True)
        os.makedirs(Config.ARCHIVE_FOLDER, exist_ok=True)
        for order_dir in ['uploads', 'converted']:
            os.makedirs(os.path.join(Config.ARCHIVE_FOLDER, order_dir), exist_ok=True)
        # 确保会话目录存在
        os.makedirs(Config.SESSION_FILE_DIR, exist_ok=True)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # 在生产环境中使用更复杂的秘钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or secrets.token_hex(16)
    
    # 会话安全配置（生产环境）
    SESSION_COOKIE_SECURE = True  # 仅通过HTTPS发送cookie
    
    # 生产环境可以使用更安全的数据库
    # SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

# 配置映射
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 