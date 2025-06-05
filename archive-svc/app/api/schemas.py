from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator


# 基础响应模型
class ResponseBase(BaseModel):
    """基础响应模型"""
    success: bool = True
    message: str = "操作成功"


class ErrorResponse(ResponseBase):
    """错误响应模型"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# 文件标签模型
class FileTagBase(BaseModel):
    """文件标签基础模型"""
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class FileTagCreate(FileTagBase):
    """创建文件标签请求模型"""
    pass


class FileTagResponse(FileTagBase):
    """文件标签响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# 归档文件模型
class ArchiveFileBase(BaseModel):
    """归档文件基础模型"""
    original_filename: str
    category: Optional[str] = "general"
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class ArchiveFileCreate(ArchiveFileBase):
    """创建归档文件请求模型"""
    file_path: str
    file_size: int
    mime_type: Optional[str] = None
    sha256_hash: str
    md5_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ArchiveFileUpdate(BaseModel):
    """更新归档文件请求模型"""
    category: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    is_deleted: Optional[bool] = None


class ArchiveFileResponse(ArchiveFileBase):
    """归档文件响应模型"""
    id: int
    stored_filename: str
    file_path: str
    file_size: int
    mime_type: Optional[str]
    sha256_hash: str
    md5_hash: Optional[str]
    archive_date: datetime
    metadata: Optional[Dict[str, Any]]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# 归档文件版本模型
class ArchiveFileVersionBase(BaseModel):
    """归档文件版本基础模型"""
    parent_id: int
    change_description: Optional[str] = None


class ArchiveFileVersionCreate(ArchiveFileVersionBase):
    """创建归档文件版本请求模型"""
    version_number: int
    stored_filename: str
    file_path: str
    file_size: int
    sha256_hash: str
    md5_hash: Optional[str] = None


class ArchiveFileVersionResponse(ArchiveFileVersionBase):
    """归档文件版本响应模型"""
    id: int
    version_number: int
    stored_filename: str
    file_path: str
    file_size: int
    sha256_hash: str
    md5_hash: Optional[str]
    version_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True


# 文件搜索请求模型
class FileSearchRequest(BaseModel):
    """文件搜索请求模型"""
    query: Optional[str] = None
    category: Optional[str] = None
    hash_value: Optional[str] = None
    tags: Optional[List[str]] = None
    skip: int = 0
    limit: int = 100


# 文件列表响应模型
class FileListResponse(ResponseBase):
    """文件列表响应模型"""
    total: int
    skip: int
    limit: int
    data: List[ArchiveFileResponse]


# 文件上传响应模型
class FileUploadResponse(ResponseBase):
    """文件上传响应模型"""
    file: ArchiveFileResponse


# 文件详情响应模型
class FileDetailResponse(ResponseBase):
    """文件详情响应模型"""
    file: ArchiveFileResponse
    versions: Optional[List[ArchiveFileVersionResponse]] = None 