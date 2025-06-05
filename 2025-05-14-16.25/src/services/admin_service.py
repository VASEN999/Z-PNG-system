from src.repositories.admin_repo import AdminRepository
from flask import session

class AdminService:
    """管理员服务类，处理与管理员用户相关的业务逻辑"""
    
    @staticmethod
    def authenticate(username, password):
        """验证用户身份
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            验证成功返回用户对象，否则返回None
        """
        user = AdminRepository.get_by_username(username)
        if user and user.check_password(password):
            # 更新最后登录时间
            AdminRepository.update_last_login(user.id)
            # 设置会话
            session['admin_id'] = user.id
            session['admin_username'] = user.username
            session['is_admin'] = user.is_admin
            return user
        return None
    
    @staticmethod
    def logout():
        """用户登出，清除会话"""
        session.pop('admin_id', None)
        session.pop('admin_username', None)
        session.pop('is_admin', None)
        
    @staticmethod
    def get_current_user():
        """获取当前登录用户"""
        return AdminRepository.get_current_user()
    
    @staticmethod
    def create_user(username, password, is_admin=False, email=None, full_name=None):
        """创建新用户
        
        Args:
            username: 用户名
            password: 密码
            is_admin: 是否为管理员
            email: 电子邮箱
            full_name: 全名
            
        Returns:
            新创建的用户对象
        """
        # 检查用户名是否已存在
        existing_user = AdminRepository.get_by_username(username)
        if existing_user:
            return None
        
        return AdminRepository.create_user(username, password, is_admin, email, full_name)
    
    @staticmethod
    def update_user(user_id, **kwargs):
        """更新用户信息"""
        return AdminRepository.update_user(user_id, **kwargs)
    
    @staticmethod
    def delete_user(user_id):
        """删除用户"""
        return AdminRepository.delete_user(user_id)
    
    @staticmethod
    def get_all_users():
        """获取所有用户"""
        return AdminRepository.get_all_users()
    
    @staticmethod
    def get_user(user_id):
        """根据ID获取用户"""
        return AdminRepository.get_by_id(user_id)
    
    @staticmethod
    def is_authenticated():
        """检查当前用户是否已登录"""
        return 'admin_id' in session
    
    @staticmethod
    def is_admin():
        """检查当前用户是否为管理员"""
        return session.get('is_admin', False)
    
    @staticmethod
    def initialize_admin():
        """初始化默认管理员账户"""
        return AdminRepository.create_default_admin() 