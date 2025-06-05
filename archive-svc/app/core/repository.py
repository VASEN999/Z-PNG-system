from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Select

from app.models.base import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """
    通用数据存储库基类，提供基础CRUD操作
    """
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        """
        根据ID获取单个对象
        
        Args:
            db: 数据库会话
            id: 对象ID
            
        Returns:
            对象实例或None
        """
        result = await db.execute(select(self.model).filter(self.model.id == id))
        return result.scalars().first()
    
    async def get_by(self, db: AsyncSession, **kwargs) -> Optional[ModelType]:
        """
        根据给定条件获取单个对象
        
        Args:
            db: 数据库会话
            **kwargs: 过滤条件
            
        Returns:
            对象实例或None
        """
        query = select(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        """
        获取多个对象
        
        Args:
            db: 数据库会话
            skip: 跳过的记录数
            limit: 返回的最大记录数
            
        Returns:
            对象列表
        """
        query = select(self.model).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    async def get_multi_by(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, **kwargs
    ) -> List[ModelType]:
        """
        根据给定条件获取多个对象
        
        Args:
            db: 数据库会话
            skip: 跳过的记录数
            limit: 返回的最大记录数
            **kwargs: 过滤条件
            
        Returns:
            对象列表
        """
        query = select(self.model).offset(skip).limit(limit)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, *, obj_in: Dict[str, Any]) -> ModelType:
        """
        创建新对象
        
        Args:
            db: 数据库会话
            obj_in: 对象数据
            
        Returns:
            创建的对象实例
        """
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self, db: AsyncSession, *, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """
        更新对象
        
        Args:
            db: 数据库会话
            db_obj: 数据库对象
            obj_in: 更新数据
            
        Returns:
            更新后的对象实例
        """
        for key, value in obj_in.items():
            if hasattr(db_obj, key):
                setattr(db_obj, key, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def delete(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        """
        删除对象
        
        Args:
            db: 数据库会话
            id: 对象ID
            
        Returns:
            被删除的对象或None
        """
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj 