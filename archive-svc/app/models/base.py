from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Integer, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from app.config import settings

# 创建异步数据库引擎
engine = create_async_engine(settings.DB_URL, echo=settings.DEBUG)

# 创建异步会话工厂
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# 创建基础模型类
Base = declarative_base()


class BaseModel(Base):
    """所有模型的基类，提供公共字段和方法"""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all) 