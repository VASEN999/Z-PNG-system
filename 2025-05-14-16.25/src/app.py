import os
import logging
from flask import Flask, session, render_template
from src.models import db
from src.api import init_app as init_blueprints, csrf
import src.settings as config

def create_app():
    """创建Flask应用实例
    
    Returns:
        Flask应用实例
    """
    # 获取项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 指定模板和静态文件目录
    template_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')
    
    # 使用自定义模板和静态文件目录创建Flask实例
    app = Flask(__name__,
                template_folder=template_dir,
                static_folder=static_dir)
    
    app.logger.info(f"模板目录: {template_dir}")
    app.logger.info(f"静态文件目录: {static_dir}")
    
    # 加载配置
    app.config.from_object(config)
    
    # 配置日志
    configure_logging(app)
    
    # 初始化扩展
    db.init_app(app)
    
    # 初始化CSRF保护
    csrf.init_app(app)
    app.logger.info(f"CSRF配置: WTF_CSRF_ENABLED={app.config.get('WTF_CSRF_ENABLED', True)}")
    
    # Flask-Session 在当前运行环境可能不可用，直接使用默认会话实现
    app.logger.info(f"Session配置: SESSION_TYPE={app.config['SESSION_TYPE']}")
    
    # 注册自定义过滤器
    register_filters(app)
    
    # 添加Jinja2模板全局函数
    register_template_globals(app)
    
    # 注册蓝图
    init_blueprints(app)
    
    # 确保上传目录存在
    with app.app_context():
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['CONVERTED_FOLDER'], exist_ok=True)
        os.makedirs(app.config['ARCHIVE_FOLDER'], exist_ok=True)
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'email_attachments'), exist_ok=True)
    
    # 注册错误处理
    register_error_handlers(app)
    
    # 打印Secret Key的前8个字符（用于调试）
    app.logger.info(f"Secret Key: {app.config['SECRET_KEY'][:8]}...")
    app.logger.info(f"运行环境: {config.ENV}")
    
    return app

def register_template_globals(app):
    """注册Jinja2模板全局函数
    
    Args:
        app: Flask应用实例
    """
    @app.context_processor
    def inject_globals():
        from src.services.admin_service import AdminService
        from src.services.order_service import OrderService
        
        def get_current_user():
            """获取当前登录用户"""
            return AdminService.get_current_user()
        
        def get_active_order(user_id=None):
            """获取用户的活跃订单"""
            if user_id is None and session.get('admin_id'):
                user_id = session.get('admin_id')
            
            if user_id:
                return OrderService.get_active_order(user_id)
            return None
        
        return {
            'get_current_user': get_current_user,
            'get_active_order': get_active_order
        }

def configure_logging(app):
    """配置应用日志
    
    Args:
        app: Flask应用实例
    """
    log_level = getattr(logging, app.config['LOG_LEVEL'])
    
    # 配置根日志
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 配置应用日志
    app_logger = logging.getLogger('app')
    app_logger.setLevel(log_level)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # 添加文件处理器
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 将处理器添加到日志记录器
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    
    # 如果配置为将日志输出到标准输出
    if app.config['LOG_TO_STDOUT']:
        app.logger.addHandler(console_handler)
    else:
        app.logger.addHandler(file_handler)

def register_error_handlers(app):
    """注册错误处理函数
    
    Args:
        app: Flask应用实例
    """
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('error.html', error_code=404, error_message='页面未找到'), 404
    
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('error.html', error_code=500, error_message='服务器内部错误'), 500
    
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('error.html', error_code=403, error_message='禁止访问'), 403 

def register_filters(app):
    """注册Jinja2自定义过滤器
    
    Args:
        app: Flask应用实例
    """
    from src.utils.filters import timeago
    
    # 添加时间相对格式化过滤器
    app.jinja_env.filters['timeago'] = timeago
    app.logger.info("已注册自定义过滤器: timeago") 