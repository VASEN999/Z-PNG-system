"""装饰器模块，提供通用的功能装饰器"""

from functools import wraps
from flask import redirect, url_for, flash, session, request

def login_required(f):
    """检查用户是否已认证的装饰器
    
    如果用户未认证，将重定向到登录页面
    
    Args:
        f: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查session中是否有admin_id
        if 'admin_id' not in session:
            flash('请先登录', 'error')
            return redirect(url_for('admin.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function 