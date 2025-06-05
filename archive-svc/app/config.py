from typing import Optional, Dict, Any, List
import os
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """应用配置设置"""
    
    # 基础配置
    APP_NAME: str = "archive-svc"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # API配置
    API_PREFIX: str = "/api"
    API_V1_STR: str = "/v1"
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8088
    
    # 安全配置
    SECRET_KEY: str = Field("insecure-change-this-key", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天
    
    # 数据库配置
    DB_TYPE: str = "sqlite"  # sqlite, mysql, postgresql
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_NAME: str = "archive_db"
    DB_URL: Optional[str] = None
    
    # 存储配置
    STORAGE_DIR: str = Field("./storage", env="STORAGE_DIR")
    ARCHIVE_DIR: str = Field("./storage/archive", env="ARCHIVE_DIR")
    TEMP_DIR: str = Field("./storage/temp", env="TEMP_DIR")
    MAX_ARCHIVE_SIZE: int = 1024 * 1024 * 100  # 100MB
    
    # 哈希配置
    HASH_ALGORITHMS: List[str] = ["sha256", "md5"]
    DEFAULT_HASH_ALGORITHM: str = "sha256"
    
    # CORS配置
    ALLOWED_HOSTS: List[str] = ["*"]
    
    @validator("DB_URL", pre=True)
    def assemble_db_url(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        """组装数据库URL"""
        if v:
            return v
        
        db_type = values.get("DB_TYPE", "sqlite")
        
        if db_type == "sqlite":
            return f"sqlite+aiosqlite:///./{values.get('DB_NAME', 'archive_db')}.db"
        
        user = values.get("DB_USER", "")
        password = values.get("DB_PASSWORD", "")
        host = values.get("DB_HOST", "localhost")
        port = values.get("DB_PORT", "")
        name = values.get("DB_NAME", "archive_db")
        
        if db_type == "mysql":
            port = port or 3306
            return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{name}"
        
        if db_type == "postgresql":
            port = port or 5432
            return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"
        
        return f"sqlite+aiosqlite:///./{name}.db"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 创建全局设置对象
settings = Settings()

# 确保存储目录存在
os.makedirs(settings.STORAGE_DIR, exist_ok=True)
os.makedirs(settings.ARCHIVE_DIR, exist_ok=True)
os.makedirs(settings.TEMP_DIR, exist_ok=True) 