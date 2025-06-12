#!/bin/bash
# 归档服务启动脚本

# 脚本路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认端口
ARCHIVE_SVC_PORT=8088

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            ARCHIVE_SVC_PORT="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}错误: 未知选项 $1${NC}"
            exit 1
            ;;
    esac
done

# 检查并结束已运行的服务进程
function stop_existing_service {
    echo -e "${YELLOW}检查并停止已运行的归档服务进程...${NC}"
    
    local PIDS=$(lsof -t -i:$ARCHIVE_SVC_PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}发现已运行的归档服务进程: $PIDS, 正在停止...${NC}"
        kill -9 $PIDS 2>/dev/null
        sleep 1
    fi
    
    echo -e "${GREEN}已停止所有归档服务进程${NC}"
}

# 停止已运行的服务进程
stop_existing_service

# 创建日志目录
mkdir -p ../logs

# 创建虚拟环境并安装依赖
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}创建归档服务虚拟环境...${NC}"
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
if [ ! -f "venv/.deps_installed" ]; then
    echo -e "${YELLOW}安装依赖...${NC}"
    # 使用虚拟环境的pip来安装包
    venv/bin/pip install --upgrade pip
    venv/bin/pip install -r requirements.txt
    venv/bin/pip install --no-cache-dir aiosqlite uvicorn
    touch venv/.deps_installed
    echo -e "${GREEN}归档服务依赖已安装${NC}"
fi

# 使用虚拟环境中的Python启动服务
echo -e "${YELLOW}正在启动归档服务在端口 $ARCHIVE_SVC_PORT...${NC}"
exec venv/bin/python run.py --host 0.0.0.0 --port $ARCHIVE_SVC_PORT 