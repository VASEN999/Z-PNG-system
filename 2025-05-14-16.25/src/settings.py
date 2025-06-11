import os
import secrets
from dotenv import load_dotenv

# 加载.env文件
load_dotenv()

# 确定环境
ENV = os.environ.get('FLASK_ENV', 'development')

# 获取项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 通用配置
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
DEBUG = ENV == 'development'
TESTING = ENV == 'testing'

# 数据库配置
if ENV == 'testing':
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite://'
elif ENV == 'production':
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "app.db")}'
else:  # development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "app_dev.db")}'

SQLALCHEMY_TRACK_MODIFICATIONS = False

# 文件上传配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
CONVERTED_FOLDER = os.path.join(BASE_DIR, 'converted')
ARCHIVE_FOLDER = os.path.join(BASE_DIR, 'archive')
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 100 * 1024 * 1024)  # 默认100MB

# 会话配置
SESSION_TYPE = os.environ.get('SESSION_TYPE') or 'filesystem'
SESSION_PERMANENT = False
SESSION_USE_SIGNER = True
SESSION_KEY_PREFIX = os.environ.get('SESSION_KEY_PREFIX') or 'file_converter_'

# 邮件配置
MAIL_SERVER = os.environ.get('MAIL_SERVER')
MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', '').lower() in ('true', '1', 'yes')
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')

# IMAP配置（用于接收邮件）
IMAP_SERVER = os.environ.get('IMAP_SERVER')
IMAP_PORT = int(os.environ.get('IMAP_PORT') or 993)
IMAP_USER = os.environ.get('IMAP_USER')
IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD')

# 日志配置
LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT', '').lower() in ('true', '1', 'yes')
LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'

# 应用配置
APP_NAME = os.environ.get('APP_NAME') or '文件转换系统'
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'

# 微服务配置
CONVERT_SVC_URL = os.environ.get('CONVERT_SVC_URL', 'http://localhost:8081')
ARCHIVE_SVC_URL = os.environ.get('ARCHIVE_SVC_URL', 'http://localhost:8088/api/v1/archive') 