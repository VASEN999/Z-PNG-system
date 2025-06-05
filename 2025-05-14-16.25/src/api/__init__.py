from flask import Blueprint
from flask_wtf.csrf import CSRFProtect

# 创建全局CSRF保护对象
csrf = CSRFProtect()

# 创建蓝图
main_bp = Blueprint('main', __name__)
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
mail_bp = Blueprint('mail', __name__, url_prefix='/mail')
orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

# 导入路由处理模块
from src.api import main_routes, admin_routes, mail_routes, order_routes

def init_app(app):
    """注册所有蓝图到应用"""
    # 注册蓝图
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(mail_bp)
    app.register_blueprint(orders_bp)
    
    # 打印蓝图注册信息
    app.logger.info("已注册蓝图: main, admin, mail, orders")
