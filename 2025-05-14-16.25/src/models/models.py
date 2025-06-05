import os
import uuid
import datetime
import bcrypt
from src.models import db

class Order(db.Model):
    """订单模型，用于管理文件上传和转换记录"""
    __tablename__ = 'orders'  # 显式指定表名，避免使用SQL保留字'order'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)  # 保留此字段以兼容现有代码
    
    # 订单状态：待处理、补材料、已审核、活跃、归档
    STATUS_PENDING = 'pending'      # 待处理
    STATUS_MATERIAL = 'material'    # 补材料
    STATUS_REVIEWED = 'reviewed'    # 已审核
    STATUS_ACTIVE = 'active'        # 活跃
    STATUS_ARCHIVED = 'archived'    # 归档
    
    status = db.Column(db.String(20), default=STATUS_PENDING)  # 默认为待处理状态
    note = db.Column(db.Text, nullable=True)
    
    # 合并订单相关字段
    is_merged = db.Column(db.Boolean, default=False)  # 是否为合并订单
    merged_from = db.Column(db.Text, nullable=True)   # 存储源订单号，以逗号分隔
    
    # 用户关联
    user_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'), nullable=True)
    user = db.relationship('AdminUser', backref='orders')
    
    # 邮件关联
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=True)
    
    # 关系
    files = db.relationship('UploadedFile', backref='order', lazy=True, cascade="all, delete-orphan")
    conversions = db.relationship('ConvertedFile', backref='order', lazy=True, cascade="all, delete-orphan")
    
    @classmethod
    def generate_order_number(cls):
        """生成唯一的订单号: 日期前缀 + UUID"""
        prefix = datetime.datetime.now().strftime('%Y%m%d')
        unique_id = uuid.uuid4().hex[:8]
        return f"{prefix}-{unique_id}"
    
    def to_dict(self):
        """将订单转换为字典"""
        return {
            'id': self.id,
            'order_number': self.order_number,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_active': self.is_active,
            'status': self.status,
            'note': self.note,
            'file_count': len(self.files),
            'conversion_count': len(self.conversions),
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'is_merged': self.is_merged,
            'merged_from': self.merged_from
        }
        
    @property
    def status_display(self):
        """返回人类可读的状态显示文本"""
        status_map = {
            self.STATUS_PENDING: '待处理',
            self.STATUS_MATERIAL: '补材料',
            self.STATUS_REVIEWED: '已审核',
            self.STATUS_ACTIVE: '活跃',
            self.STATUS_ARCHIVED: '归档'
        }
        return status_map.get(self.status, '未知状态')
    
    @property
    def source_orders(self):
        """获取合并来源的订单对象列表"""
        if not self.merged_from:
            return []
        order_numbers = self.merged_from.split(',')
        return Order.query.filter(Order.order_number.in_(order_numbers)).all()

class UploadedFile(db.Model):
    """上传的文件模型"""
    __tablename__ = 'uploaded_files'  # 显式指定表名
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # 存储的文件名
    original_filename = db.Column(db.String(255), nullable=False)  # 原始文件名
    file_path = db.Column(db.String(255), nullable=False)  # 文件路径
    file_size = db.Column(db.Integer, nullable=True)  # 文件大小
    file_type = db.Column(db.String(50), nullable=True)  # 文件类型
    file_hash = db.Column(db.String(64), nullable=True)  # 文件哈希值，用于唯一标识文件内容
    upload_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)  # 修改为新表名
    
    # 定义与转换文件的关系
    conversions = db.relationship('ConvertedFile', backref='source_file', lazy=True, 
                                 foreign_keys='ConvertedFile.source_file_id', cascade="all, delete-orphan")
    
    def to_dict(self):
        """将文件转换为字典"""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'file_hash': self.file_hash,
            'upload_time': self.upload_time.strftime('%Y-%m-%d %H:%M:%S'),
            'order_number': self.order.order_number if self.order else None
        }

class ConvertedFile(db.Model):
    """转换后的文件模型"""
    __tablename__ = 'converted_files'  # 显式指定表名
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    source_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_files.id'), nullable=True)  # 修改为新表名
    source_hash = db.Column(db.String(64), nullable=True)  # 源文件的哈希值，用于间接映射
    from_zip = db.Column(db.Boolean, default=False)  # 是否来自压缩包
    zip_path = db.Column(db.String(255), nullable=True)  # 所属压缩包路径
    conversion_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)  # 修改为新表名
    
    def to_dict(self):
        """将转换文件转换为字典"""
        return {
            'id': self.id,
            'filename': self.filename,
            'file_path': self.file_path,
            'source_hash': self.source_hash,
            'from_zip': self.from_zip,
            'zip_path': self.zip_path,
            'conversion_time': self.conversion_time.strftime('%Y-%m-%d %H:%M:%S'),
            'order_number': self.order.order_number if self.order else None,
            'source_filename': self.source_file.filename if self.source_file else None
        }

class AdminUser(db.Model):
    """用户模型，包含管理员和普通用户"""
    __tablename__ = 'admin_user'  # 显式指定表名
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # 默认为普通用户
    email = db.Column(db.String(100), nullable=True)
    full_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)  # 账户是否激活
    
    def set_password(self, password):
        """设置密码"""
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    def check_password(self, password):
        """验证密码"""
        password_bytes = password.encode('utf-8')
        hash_bytes = self.password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)
    
    @classmethod
    def create_default_admin(cls):
        """创建默认管理员用户"""
        default_admin = cls.query.filter_by(username='admin').first()
        if not default_admin:
            default_admin = cls(
                username='admin', 
                is_admin=True,
                full_name='系统管理员',
                email='admin@example.com'
            )
            default_admin.set_password('admin123')
            db.session.add(default_admin)
            db.session.commit()
            return default_admin
        return default_admin 
        
    def to_dict(self):
        """将用户转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin,
            'email': self.email,
            'full_name': self.full_name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'is_active': self.is_active
        }

class Email(db.Model):
    """邮件模型，用于存储和管理接收到的邮件"""
    __tablename__ = 'emails'
    
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(100), nullable=False)  # 邮件UID，用于标识邮件
    subject = db.Column(db.String(255), nullable=False)  # 邮件主题
    sender = db.Column(db.String(100), nullable=False)   # 发件人邮箱
    sender_name = db.Column(db.String(100), nullable=True)  # 发件人名称
    received_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)  # 接收时间
    content = db.Column(db.Text, nullable=True)         # 邮件内容
    processed = db.Column(db.Boolean, default=False)    # 是否已处理
    assigned_to = db.Column(db.Integer, db.ForeignKey('admin_user.id'), nullable=True)  # 分配给谁
    
    # 使用uid和subject的组合作为唯一约束，确保不会重复处理相同的邮件
    __table_args__ = (
        db.UniqueConstraint('uid', 'subject', name='_uid_subject_uc'),
    )
    
    # 关系
    attachments = db.relationship('EmailAttachment', backref='email', lazy=True, cascade="all, delete-orphan")
    processor = db.relationship('AdminUser', backref='assigned_emails', foreign_keys=[assigned_to])
    orders = db.relationship('Order', backref='source_email', foreign_keys=[Order.email_id])
    
    def to_dict(self):
        """将邮件转换为字典"""
        return {
            'id': self.id,
            'uid': self.uid,
            'subject': self.subject,
            'sender': self.sender,
            'sender_name': self.sender_name,
            'received_at': self.received_at.strftime('%Y-%m-%d %H:%M:%S'),
            'processed': self.processed,
            'assigned_to': self.assigned_to,
            'processor_name': self.processor.username if self.processor else None,
            'attachment_count': len(self.attachments)
        }

class EmailAttachment(db.Model):
    """邮件附件模型，存储邮件中的附件文件信息"""
    __tablename__ = 'email_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # 原始附件文件名
    saved_as = db.Column(db.String(255), nullable=False)  # 保存的文件名
    file_path = db.Column(db.String(255), nullable=False)  # 附件存储路径
    file_size = db.Column(db.Integer, nullable=True)      # 附件大小
    file_type = db.Column(db.String(50), nullable=True)   # 附件类型
    file_hash = db.Column(db.String(64), nullable=True)   # 附件哈希值
    email_id = db.Column(db.Integer, db.ForeignKey('emails.id'), nullable=False)  # 所属邮件ID
    
    def to_dict(self):
        """将附件转换为字典"""
        return {
            'id': self.id,
            'filename': self.filename,
            'saved_as': self.saved_as,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'email_id': self.email_id
        } 