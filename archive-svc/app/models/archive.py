from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class ArchiveFile(BaseModel):
    """归档文件模型"""
    
    __tablename__ = "archive_files"
    
    # 文件信息
    original_filename = Column(String(255), nullable=False, index=True)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    mime_type = Column(String(128), nullable=True)
    
    # 哈希信息
    sha256_hash = Column(String(64), nullable=False, index=True)
    md5_hash = Column(String(32), nullable=True, index=True)
    
    # 归档信息
    archive_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = Column(String(64), nullable=True, index=True)
    tags = Column(JSON, nullable=True)  # JSON格式存储标签列表
    
    # 元数据
    file_metadata = Column(JSON, nullable=True)  # 存储文件元数据
    description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    # 关联关系
    versions = relationship("ArchiveFileVersion", back_populates="parent_file")
    
    def __repr__(self):
        return f"<ArchiveFile(id={self.id}, original_filename='{self.original_filename}', sha256_hash='{self.sha256_hash[:8]}...')>"


class ArchiveFileVersion(BaseModel):
    """归档文件版本模型，用于跟踪文件的历史版本"""
    
    __tablename__ = "archive_file_versions"
    
    parent_id = Column(Integer, ForeignKey("archive_files.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    
    # 哈希信息
    sha256_hash = Column(String(64), nullable=False, index=True)
    md5_hash = Column(String(32), nullable=True)
    
    # 版本信息
    version_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    change_description = Column(Text, nullable=True)
    
    # 关联关系
    parent_file = relationship("ArchiveFile", back_populates="versions")
    
    def __repr__(self):
        return f"<ArchiveFileVersion(id={self.id}, parent_id={self.parent_id}, version_number={self.version_number})>"


class FileTag(BaseModel):
    """文件标签模型"""
    
    __tablename__ = "file_tags"
    
    name = Column(String(64), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # HEX颜色代码，如 #FF0000
    
    def __repr__(self):
        return f"<FileTag(id={self.id}, name='{self.name}')>" 