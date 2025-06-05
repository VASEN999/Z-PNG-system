from typing import Dict, List, Optional, Any
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repository import BaseRepository
from app.models.archive import ArchiveFile, ArchiveFileVersion, FileTag


class ArchiveFileRepository(BaseRepository[ArchiveFile]):
    """归档文件仓库"""
    
    def __init__(self):
        super().__init__(ArchiveFile)
    
    async def get_by_hash(self, db: AsyncSession, hash_value: str) -> Optional[ArchiveFile]:
        """
        根据哈希值获取文件
        
        Args:
            db: 数据库会话
            hash_value: 哈希值
            
        Returns:
            文件对象或None
        """
        result = await db.execute(
            select(self.model).filter(
                or_(
                    self.model.sha256_hash == hash_value,
                    self.model.md5_hash == hash_value
                )
            ).filter(self.model.is_deleted == False)
        )
        return result.scalars().first()
    
    async def search_files(
        self,
        db: AsyncSession,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
        hash_value: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ArchiveFile]:
        """
        搜索文件
        
        Args:
            db: 数据库会话
            query: 搜索关键词（在文件名中）
            category: 文件分类
            hash_value: 哈希值
            tags: 标签列表
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            文件列表
        """
        filters = [self.model.is_deleted == False]
        
        if query:
            filters.append(self.model.original_filename.ilike(f"%{query}%"))
        
        if category:
            filters.append(self.model.category == category)
        
        if hash_value:
            filters.append(
                or_(
                    self.model.sha256_hash == hash_value,
                    self.model.md5_hash == hash_value
                )
            )
        
        # 复杂过滤：标签过滤 (通过JSON字段)
        if tags:
            for tag in tags:
                # 对于PostgreSQL和MySQL，可以使用JSON包含操作符
                # 这里使用了一个简化的方法，可能需要根据具体数据库进行调整
                filters.append(self.model.tags.contains(tag))
        
        query = select(self.model).filter(and_(*filters)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def soft_delete(self, db: AsyncSession, *, id: int) -> Optional[ArchiveFile]:
        """
        软删除文件（设置is_deleted标志）
        
        Args:
            db: 数据库会话
            id: 文件ID
            
        Returns:
            更新后的文件对象或None
        """
        obj = await self.get(db, id)
        if obj:
            return await self.update(db, db_obj=obj, obj_in={"is_deleted": True})
        return None


class ArchiveFileVersionRepository(BaseRepository[ArchiveFileVersion]):
    """归档文件版本仓库"""
    
    def __init__(self):
        super().__init__(ArchiveFileVersion)
    
    async def get_versions_by_parent(
        self, db: AsyncSession, parent_id: int, skip: int = 0, limit: int = 100
    ) -> List[ArchiveFileVersion]:
        """
        获取文件的所有版本
        
        Args:
            db: 数据库会话
            parent_id: 父文件ID
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            版本列表
        """
        query = (
            select(self.model)
            .filter(self.model.parent_id == parent_id)
            .order_by(self.model.version_number.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_latest_version(
        self, db: AsyncSession, parent_id: int
    ) -> Optional[ArchiveFileVersion]:
        """
        获取文件的最新版本
        
        Args:
            db: 数据库会话
            parent_id: 父文件ID
            
        Returns:
            最新版本或None
        """
        query = (
            select(self.model)
            .filter(self.model.parent_id == parent_id)
            .order_by(self.model.version_number.desc())
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalars().first()


class FileTagRepository(BaseRepository[FileTag]):
    """文件标签仓库"""
    
    def __init__(self):
        super().__init__(FileTag)
    
    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[FileTag]:
        """
        根据名称获取标签
        
        Args:
            db: 数据库会话
            name: 标签名称
            
        Returns:
            标签对象或None
        """
        return await self.get_by(db, name=name)


# 创建仓库实例
archive_file_repo = ArchiveFileRepository()
archive_file_version_repo = ArchiveFileVersionRepository()
file_tag_repo = FileTagRepository() 