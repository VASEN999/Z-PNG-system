from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import time
from typing import Dict, Any

from app.models import get_db
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查接口，返回服务状态
    """
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "name": settings.APP_NAME,
        "timestamp": int(time.time()),
    }


@router.get("/health/db")
async def db_health_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    数据库健康检查，检查数据库连接是否正常
    """
    try:
        # 执行一个简单的SQL查询来检查数据库连接
        await db.execute("SELECT 1")
        db_status = "ok"
        error = None
    except Exception as e:
        db_status = "error"
        error = str(e)
    
    return {
        "status": "ok" if db_status == "ok" else "error",
        "database": {
            "status": db_status,
            "type": settings.DB_TYPE,
            "error": error,
        },
        "timestamp": int(time.time()),
    } 