from src.models import db
from src.models.models import AdminUser
from flask import session

class AdminRepository:
    """管理员用户存储库类，处理与管理员用户相关的数据库操作"""
    
    @staticmethod
    def get_by_id(user_id):
        """根据ID获取用户"""
        return AdminUser.query.get(user_id)
    
    @staticmethod
    def get_by_username(username):
        """根据用户名获取用户"""
        return AdminUser.query.filter_by(username=username).first()
    
    @staticmethod
    def get_all_users():
        """获取所有用户"""
        return AdminUser.query.all()
    
    @staticmethod
    def get_current_user():
        """获取当前登录用户"""
        user_id = session.get('admin_id')
        if user_id:
            return AdminUser.query.get(user_id)
        return None
    
    @staticmethod
    def create_user(username, password, is_admin=False, email=None, full_name=None):
        """创建新用户"""
        user = AdminUser(
            username=username,
            is_admin=is_admin,
            email=email,
            full_name=full_name
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    
    @staticmethod
    def update_user(user_id, **kwargs):
        """更新用户信息"""
        user = AdminUser.query.get(user_id)
        if user:
            for key, value in kwargs.items():
                if key == 'password':
                    user.set_password(value)
                elif hasattr(user, key):
                    setattr(user, key, value)
            db.session.commit()
        return user
    
    @staticmethod
    def update_last_login(user_id):
        """更新用户最后登录时间"""
        from datetime import datetime
        user = AdminUser.query.get(user_id)
        if user:
            user.last_login = datetime.utcnow()
            db.session.commit()
    
    @staticmethod
    def delete_user(user_id):
        """删除用户"""
        user = AdminUser.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def create_default_admin():
        """创建默认管理员账户"""
        return AdminUser.create_default_admin() 