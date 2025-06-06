from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import time

from app.api.routes import archive_router, health_router
from app.models import init_db
from app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("archive-svc")


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例
    
    Returns:
        FastAPI应用
    """
    # 创建应用
    app = FastAPI(
        title=settings.APP_NAME,
        description="文件归档与哈希检索服务API",
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(
        health_router,
        prefix=f"{settings.API_PREFIX}{settings.API_V1_STR}",
        tags=["健康检查"],
    )
    app.include_router(
        archive_router,
        prefix=f"{settings.API_PREFIX}{settings.API_V1_STR}/archive",
        tags=["文件归档"],
    )
    
    # 添加根路径健康检查端点，与启动脚本兼容
    @app.get("/health")
    async def root_health_check():
        return {
            "status": "ok",
            "service": settings.APP_NAME,
            "timestamp": int(time.time()),
        }
    
    # 添加启动事件
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"启动应用: {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"初始化数据库...")
        await init_db()
        logger.info(f"数据库初始化完成")
    
    # 添加关闭事件
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info(f"关闭应用: {settings.APP_NAME}")
    
    return app


app = create_app()

if __name__ == "__main__":
    # 直接启动服务器
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    ) 