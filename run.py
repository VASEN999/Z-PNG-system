#!/usr/bin/env python3
"""
文件转换系统启动脚本 - 主目录入口
"""
import os
import sys
import subprocess
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("startup")

# 定义项目目录
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '2025-05-14-16.25')

def main():
    """
    主函数：切换到项目目录并启动应用
    """
    logger.info(f"启动文件转换系统")
    logger.info(f"切换到项目目录: {PROJECT_DIR}")
    
    # 检查项目目录是否存在
    if not os.path.isdir(PROJECT_DIR):
        logger.error(f"错误: 项目目录不存在 {PROJECT_DIR}")
        print(f"错误: 项目目录不存在 {PROJECT_DIR}")
        sys.exit(1)
    
    # 切换到项目目录
    os.chdir(PROJECT_DIR)
    
    # 将项目目录添加到Python路径
    sys.path.insert(0, PROJECT_DIR)
    
    try:
        # 检查是否存在虚拟环境
        venv_path = os.path.join(PROJECT_DIR, "venv_local")
        if os.path.exists(venv_path):
            logger.info(f"使用虚拟环境: {venv_path}")
            if sys.platform == 'win32':
                python_exe = os.path.join(venv_path, 'Scripts', 'python.exe')
            else:
                python_exe = os.path.join(venv_path, 'bin', 'python')
        else:
            logger.info(f"使用系统Python")
            python_exe = sys.executable
        
        # 直接运行项目目录下的run.py
        run_script = os.path.join(PROJECT_DIR, "run.py")
        if os.path.exists(run_script):
            logger.info(f"运行脚本: {run_script}")
            print(f"正在启动应用...")
            subprocess.call([python_exe, run_script])
        else:
            logger.error(f"错误: 找不到运行脚本 {run_script}")
            print(f"错误: 找不到运行脚本 {run_script}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"运行错误: {e}", exc_info=True)
        print(f"运行错误: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 