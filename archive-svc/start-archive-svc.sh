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

# 配置选项
HOST="0.0.0.0"
PORT=8000
DEBUG=false
RELOAD=false
VENV_DIR="venv"

# 帮助信息
function show_help {
    echo -e "${BLUE}归档服务启动脚本${NC}"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help             显示帮助信息"
    echo "  -d, --debug            启用调试模式"
    echo "  -r, --reload           启用热重载（开发模式）"
    echo "  -p, --port PORT        指定端口（默认: 8000）"
    echo "  --host HOST            指定主机地址（默认: 0.0.0.0）"
    echo "  --install              安装依赖"
    echo "  --venv DIR             指定虚拟环境目录（默认: venv）"
    echo ""
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--debug)
            DEBUG=true
            shift
            ;;
        -r|--reload)
            RELOAD=true
            shift
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --install)
            INSTALL=true
            shift
            ;;
        --venv)
            VENV_DIR="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}错误: 未知选项 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 创建虚拟环境（如果不存在）
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}虚拟环境不存在，创建中...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}虚拟环境创建失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}虚拟环境创建成功${NC}"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
    echo -e "${RED}虚拟环境激活失败${NC}"
    exit 1
fi

# 安装依赖
if [ "$INSTALL" = true ]; then
    echo -e "${YELLOW}安装依赖...${NC}"
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}依赖安装失败${NC}"
        exit 1
    fi
    echo -e "${GREEN}依赖安装成功${NC}"
fi

# 构建启动命令
CMD="./run.py"

if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

if [ "$RELOAD" = true ]; then
    CMD="$CMD --reload"
fi

CMD="$CMD --host $HOST --port $PORT"

# 创建目录结构
mkdir -p storage/{archive,temp}

# 启动服务
echo -e "${BLUE}启动归档服务...${NC}"
echo -e "${YELLOW}命令: $CMD${NC}"
$CMD

# 捕获退出码
EXIT_CODE=$?

# 如果服务异常退出，显示错误信息
if [ $EXIT_CODE -ne 0 ]; then
    echo -e "${RED}服务异常退出，退出码: $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi 