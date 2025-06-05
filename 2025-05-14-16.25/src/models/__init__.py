from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例
db = SQLAlchemy()

from src.models.models import AdminUser, UploadedFile, ConvertedFile, Order
