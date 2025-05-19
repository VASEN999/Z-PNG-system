import os
import logging
from datetime import datetime
from flask import Flask, session
from flask_wtf.csrf import CSRFProtect  # 导入CSRF保护
from flask_session import Session  # 导入Session扩展
from models import db
import secrets

# 创建全局CSRF保护对象
csrf = CSRFProtect()

def create_app(config_object):
    """应用工厂函数，创建Flask应用实例"""
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # 初始化数据库
    db.init_app(app)
    
    # 启用CSRF保护
    csrf.init_app(app)
    
    # 初始化服务器端会话
    Session(app)
    
    # 创建会话文件存储目录
    if app.config['SESSION_TYPE'] == 'filesystem':
        os.makedirs(app.config.get('SESSION_FILE_DIR', 'flask_session'), exist_ok=True)
    
    # 确保所需目录存在
    config_object.init_app(app)
    
    # 设置日志
    setup_logging(app)
    
    # 添加模板上下文处理器
    setup_template_context(app)
    
    # 注册蓝图
    register_blueprints(app)
    
    # 打印会话配置，便于调试
    app.logger.info(f"Secret Key: {app.config.get('SECRET_KEY')[:8]}...")
    app.logger.info(f"Session配置: SESSION_TYPE={app.config.get('SESSION_TYPE')}")
    app.logger.info(f"CSRF配置: WTF_CSRF_ENABLED={app.config.get('WTF_CSRF_ENABLED')}")
    
    # 添加一个测试路由，检查会话功能
    @app.route('/test_session')
    def test_session():
        session['test'] = 'Session works!'
        return 'Session test initiated. Go to /check_session to verify.'
    
    @app.route('/check_session')
    def check_session():
        return f"Session value: {session.get('test', 'Not found')}"
    
    # 修复CSRF配置的路由
    @app.route('/fix_csrf')
    def fix_csrf():
        new_secret_key = secrets.token_hex(16)
        app.config['SECRET_KEY'] = new_secret_key
        app.logger.info(f"新的Secret Key: {new_secret_key[:8]}...")
        return 'CSRF configuration fixed. Try logging in again.'
    
    # 如果不是测试模式，启动邮件检查线程
    if not app.testing:
        try:
            from app.mail.routes import start_mail_thread
            app.logger.info("启动邮件检查线程...")
            start_mail_thread(app)
        except Exception as e:
            app.logger.error(f"启动邮件检查线程失败: {str(e)}")
    
    # 设置静态文件目录
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
    app.config['CONVERTED_FOLDER'] = os.path.join(app.instance_path, 'converted')
    app.config['ARCHIVE_FOLDER'] = os.path.join(app.instance_path, 'archive')
    app.config['TEMP_FOLDER'] = os.path.join(app.instance_path, 'temp')  # 新增临时文件夹配置
    
    # 确保目录存在
    for folder in [app.config['UPLOAD_FOLDER'], app.config['CONVERTED_FOLDER'], 
                   app.config['ARCHIVE_FOLDER'], app.config['TEMP_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    
    return app

def setup_logging(app):
    """设置应用日志"""
    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app.log"),
            logging.StreamHandler()
        ]
    )
    app.logger.setLevel(log_level)

def setup_template_context(app):
    """设置Jinja2模板上下文处理器"""
    @app.context_processor
    def inject_now():
        return {'now': datetime.utcnow()}
        
    @app.context_processor
    def inject_functions():
        from models import AdminUser, Order
        
        def get_current_user():
            """获取当前登录的用户对象"""
            from flask import session
            if 'admin_id' in session:
                return AdminUser.query.get(session['admin_id'])
            return None
        
        def get_db():
            """获取数据库对象，供模板使用"""
            return db
        
        def get_active_order(user_id):
            """获取用户当前活跃订单"""
            from models import Order
            return Order.query.filter_by(is_active=True, user_id=user_id).first()
            
        return dict(
            get_current_user=get_current_user, 
            get_db=get_db,
            get_active_order=get_active_order,
            Order=Order
        )

def register_blueprints(app):
    """注册所有蓝图"""
    from app.main import main_bp
    from app.admin import admin_bp
    from app.orders import orders_bp
    from app.mail import mail_bp  # 导入邮件蓝图
    
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(mail_bp, url_prefix='/mail')  # 注册邮件蓝图 