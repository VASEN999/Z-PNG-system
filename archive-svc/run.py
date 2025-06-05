#!/usr/bin/env python3
"""
归档服务启动脚本
"""
import uvicorn
import argparse
import logging
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("archive-svc-starter")

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="归档服务启动脚本")
    parser.add_argument(
        "--host",
        type=str,
        default=settings.HOST,
        help="服务器监听地址"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.PORT,
        help="服务器监听端口"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="是否启用热重载（开发模式）"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="是否启用调试模式"
    )
    
    args = parser.parse_args()
    
    logger.info("正在启动归档服务...")
    logger.info(f"主机: {args.host}")
    logger.info(f"端口: {args.port}")
    logger.info(f"热重载: {args.reload}")
    logger.info(f"调试模式: {args.debug}")
    
    # 启动服务器
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.debug else "info",
    )

if __name__ == "__main__":
    main() 