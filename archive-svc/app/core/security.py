from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

from jose import jwt
from passlib.context import CryptContext

from app.config import settings

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 签名算法
ALGORITHM = "HS256"


def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌
    
    Args:
        subject: 令牌主题（通常是用户ID）
        expires_delta: 过期时间增量
        
    Returns:
        jwt令牌字符串
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        密码哈希值
    """
    return pwd_context.hash(password) 