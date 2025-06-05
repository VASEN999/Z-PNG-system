#!/usr/bin/env python3
# 主目录启动文件 - 导入并运行src目录下的实际run.py

import os
import sys

# 确保当前目录在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导入src目录中的run.py
from src.run import *

# 这个脚本主要作为入口点，实际执行的是src/run.py中的代码
if __name__ == '__main__':
    # 确保目录存在
    ensure_directories_exist()
    
    # 获取数据库路径
    db_path = config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    
    # 检查是否需要重置数据库
    reset_db = os.environ.get('RESET_DB', 'false').lower() == 'true'
    
    if reset_db and os.path.exists(db_path) and db_path != ':memory:':
        logger.info(f"删除数据库文件: {db_path}")
        os.remove(db_path)
    
    # 创建新的数据库及表
    with app.app_context():
        logger.info("创建新的数据库结构...")
        db.create_all()
        # 使用配置中的默认管理员信息
        default_admin = AdminUser.query.filter_by(username=config.ADMIN_USERNAME).first()
        if not default_admin:
            default_admin = AdminUser(
                username=config.ADMIN_USERNAME,
                is_admin=True,
                full_name='系统管理员',
                email=config.ADMIN_EMAIL
            )
            default_admin.set_password(config.ADMIN_PASSWORD)
            db.session.add(default_admin)
            db.session.commit()
            logger.info(f"创建默认管理员: {config.ADMIN_USERNAME}")
        logger.info("数据库初始化完成")
    
    # 启动Flask应用
    # 使用0.0.0.0允许局域网访问
    host = '0.0.0.0'
    
    # 尝试使用用户指定的端口，如果不可用则自动查找可用端口
    preferred_port = int(os.environ.get('PORT', 8080))
    if not is_port_available(preferred_port, host):
        logger.warning(f"端口 {preferred_port} 已被占用，正在查找可用端口...")
        port = find_available_port(8001)
        logger.info(f"自动选择端口 {port}")
    else:
        port = preferred_port
        
    debug = config.DEBUG
    
    logger.info(f"应用启动于 http://{host}:{port}，debug={debug}")
    print(f"应用已启动，请访问: http://{host}:{port}")
    
    # 使用threaded=True提高并发性能
    app.run(host=host, port=port, debug=debug, threaded=True) 