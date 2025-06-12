#!/bin/bash
# 启动所有服务的集成脚本

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
DEBUG=false
MAIN_APP_PORT=8080
CONVERT_SVC_PORT=8081
ARCHIVE_SVC_PORT=8088
INSTALL_DEPS=false

# 帮助信息
function show_help {
    echo -e "${BLUE}文件转换系统集成启动脚本${NC}"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help             显示帮助信息"
    echo "  -d, --debug            启用调试模式"
    echo "  --install              安装依赖"
    echo "  --main-port PORT       主应用端口（默认: 8080）"
    echo "  --convert-port PORT    转换服务端口（默认: 8081）"
    echo "  --archive-port PORT    归档服务端口（默认: 8088）"
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
        --install)
            INSTALL_DEPS=true
            shift
            ;;
        --main-port)
            MAIN_APP_PORT="$2"
            shift 2
            ;;
        --convert-port)
            CONVERT_SVC_PORT="$2"
            shift 2
            ;;
        --archive-port)
            ARCHIVE_SVC_PORT="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}错误: 未知选项 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 检查并安装依赖
if [ "$INSTALL_DEPS" = true ]; then
    echo -e "${YELLOW}安装Python依赖...${NC}"
    pip install -r 2025-05-14-16.25/src/requirements.txt
    pip install -r archive-svc/requirements.txt
    
    echo -e "${YELLOW}安装Go依赖...${NC}"
    cd convert-svc
    go mod download
    cd ..
    
    echo -e "${GREEN}依赖安装完成${NC}"
fi

# 检查并构建转换服务二进制文件
function build_convert_service {
    echo -e "${YELLOW}检测到转换服务二进制文件不存在，尝试构建...${NC}"
    
    # 检查是否安装了Go
    if ! command -v go &> /dev/null; then
        echo -e "${RED}错误: 未安装Go运行时，无法构建转换服务${NC}"
        echo -e "${YELLOW}请安装Go (https://golang.org/doc/install) 后重试${NC}"
        exit 1
    fi
    
    # 构建转换服务
    cd convert-svc
    echo -e "${YELLOW}下载Go依赖...${NC}"
    go mod tidy
    
    echo -e "${YELLOW}编译转换服务...${NC}"
    go build -o convert-svc
    
    # 检查构建结果
    if [ $? -ne 0 ] || [ ! -f "convert-svc" ]; then
        echo -e "${RED}错误: 转换服务构建失败${NC}"
        cd ..
        exit 1
    fi
    
    chmod +x convert-svc
    echo -e "${GREEN}转换服务构建成功${NC}"
    cd ..
}

# 检查必要服务和文件
function check_requirements {
    # 检查转换服务
    if [ ! -f "convert-svc/convert-svc" ] || [ ! -x "convert-svc/convert-svc" ]; then
        echo -e "${YELLOW}转换服务(convert-svc)不存在或不可执行${NC}"
        build_convert_service
    fi
    
    # 检查归档服务
    if [ ! -f "archive-svc/run.py" ] || [ ! -x "archive-svc/run.py" ]; then
        echo -e "${RED}错误: 归档服务(archive-svc)不存在或不可执行${NC}"
        echo -e "请确保archive-svc目录下有可执行的run.py文件"
        exit 1
    fi
    
    # 检查主应用
    if [ ! -f "2025-05-14-16.25/run.py" ]; then
        echo -e "${RED}错误: 主应用(run.py)不存在${NC}"
        echo -e "请确保2025-05-14-16.25目录下有run.py文件"
        exit 1
    fi
    
    # 添加执行权限
    chmod +x convert-svc/convert-svc
    chmod +x archive-svc/run.py
    chmod +x archive-svc/start-archive-svc.sh
    chmod +x 2025-05-14-16.25/run.py
}

# 创建日志目录
mkdir -p logs

# 检查并结束已运行的服务进程
function stop_existing_services {
    echo -e "${YELLOW}检查并停止已运行的服务进程...${NC}"
    
    # 检查并结束转换服务
    local CONVERT_PIDS=$(lsof -t -i:$CONVERT_SVC_PORT 2>/dev/null)
    if [ -n "$CONVERT_PIDS" ]; then
        echo -e "${YELLOW}发现已运行的转换服务进程: $CONVERT_PIDS, 正在停止...${NC}"
        kill -9 $CONVERT_PIDS 2>/dev/null
        sleep 1
    fi
    
    # 检查并结束归档服务
    local ARCHIVE_PIDS=$(lsof -t -i:$ARCHIVE_SVC_PORT 2>/dev/null)
    if [ -n "$ARCHIVE_PIDS" ]; then
        echo -e "${YELLOW}发现已运行的归档服务进程: $ARCHIVE_PIDS, 正在停止...${NC}"
        kill -9 $ARCHIVE_PIDS 2>/dev/null
        sleep 1
    fi
    
    # 检查并结束主应用
    local MAIN_PIDS=$(lsof -t -i:$MAIN_APP_PORT 2>/dev/null)
    if [ -n "$MAIN_PIDS" ]; then
        echo -e "${YELLOW}发现已运行的主应用进程: $MAIN_PIDS, 正在停止...${NC}"
        kill -9 $MAIN_PIDS 2>/dev/null
        sleep 1
    fi
    
    echo -e "${GREEN}所有已运行的服务进程已停止${NC}"
}

# 检查必要条件
check_requirements

# 停止已运行的服务进程
stop_existing_services

# 设置环境变量
export PORT=$MAIN_APP_PORT
export CONVERT_SVC_URL="http://localhost:$CONVERT_SVC_PORT"
export ARCHIVE_SVC_URL="http://localhost:$ARCHIVE_SVC_PORT/api/v1/archive"

echo -e "${BLUE}启动所有服务...${NC}"
echo -e "${YELLOW}主应用端口: $MAIN_APP_PORT${NC}"
echo -e "${YELLOW}转换服务端口: $CONVERT_SVC_PORT${NC}"
echo -e "${YELLOW}归档服务端口: $ARCHIVE_SVC_PORT${NC}"

# 启动转换服务
echo -e "${YELLOW}启动转换服务...${NC}"
cd convert-svc

# 确保存储目录存在并有正确的权限
echo -e "${YELLOW}确保转换服务存储目录存在...${NC}"
mkdir -p storage/uploads storage/converted storage/archive
chmod -R 755 storage

# 直接启动二进制文件，使用默认配置，不提供端口参数
nohup ./convert-svc > ../logs/convert-svc.log 2>&1 &
CONVERT_PID=$!
cd ..
echo -e "${GREEN}转换服务已启动，PID: $CONVERT_PID${NC}"

# 启动归档服务
echo -e "${YELLOW}启动归档服务...${NC}"

# 使用新创建的启动脚本
nohup ./archive-svc/start-archive-svc.sh --port $ARCHIVE_SVC_PORT > logs/archive-svc.log 2>&1 &
ARCHIVE_PID=$!
echo -e "${GREEN}归档服务已启动，PID: $ARCHIVE_PID${NC}"

# 等待几秒以确保服务启动完成
sleep 5

# 检查进程是否运行
ps -p $CONVERT_PID > /dev/null || { echo -e "${RED}转换服务进程未启动!${NC}"; }
ps -p $ARCHIVE_PID > /dev/null || { echo -e "${RED}归档服务进程未启动!${NC}"; }

# 检查转换服务健康状态
echo -e "${YELLOW}检查转换服务健康状态...${NC}"
CONVERT_HEALTH_CHECK=false
for i in {1..5}; do
    # 首先尝试/api/health端点
    if curl -s "http://localhost:$CONVERT_SVC_PORT/api/health" | grep -q "ok"; then
        CONVERT_HEALTH_CHECK=true
        echo -e "${GREEN}转换服务健康检查通过 (/api/health)${NC}"
        break
    # 然后尝试/health端点
    elif curl -s "http://localhost:$CONVERT_SVC_PORT/health" | grep -q "ok"; then
        CONVERT_HEALTH_CHECK=true
        echo -e "${GREEN}转换服务健康检查通过 (/health)${NC}"
        break
    fi
    echo -e "${YELLOW}等待转换服务启动 ($i/5)...${NC}"
    sleep 2
done

# 检查归档服务健康状态
echo -e "${YELLOW}检查归档服务健康状态...${NC}"
ARCHIVE_HEALTH_CHECK=false
for i in {1..5}; do
    if curl -s "http://localhost:$ARCHIVE_SVC_PORT/health" | grep -q "ok"; then
        ARCHIVE_HEALTH_CHECK=true
        echo -e "${GREEN}归档服务健康检查通过${NC}"
        break
    fi
    echo -e "${YELLOW}等待归档服务启动 ($i/5)...${NC}"
    sleep 2
done

# 输出健康检查结果
if [ "$CONVERT_HEALTH_CHECK" = false ]; then
    echo -e "${RED}转换服务健康检查失败，请检查日志: logs/convert-svc.log${NC}"
fi

if [ "$ARCHIVE_HEALTH_CHECK" = false ]; then
    echo -e "${RED}归档服务健康检查失败，请检查日志: logs/archive-svc.log${NC}"
fi

# 启动主应用
echo -e "${YELLOW}启动主应用...${NC}"
cd 2025-05-14-16.25

# 确保之前修改的环境变量正确传递
echo -e "${YELLOW}设置主应用环境变量:${NC}"
echo -e "  CONVERT_SVC_URL=$CONVERT_SVC_URL"
echo -e "  ARCHIVE_SVC_URL=$ARCHIVE_SVC_URL"

# 使用PYTHONPATH确保src模块能被导入
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 仅当转换服务和归档服务都就绪时才启动主应用
if [ "$CONVERT_HEALTH_CHECK" = true ] && [ "$ARCHIVE_HEALTH_CHECK" = true ]; then
    # 在后台运行主应用
    nohup python run.py > ../logs/main-app.log 2>&1 &
    MAIN_PID=$!
    echo -e "${GREEN}主应用已启动，PID: $MAIN_PID${NC}"
    # 检查主应用是否运行
    sleep 5
    if ps -p $MAIN_PID > /dev/null; then
        echo -e "${GREEN}主应用已成功启动${NC}"
    else
        echo -e "${RED}主应用进程未启动成功!${NC}"
    fi
else
    echo -e "${RED}依赖服务未就绪，主应用未启动${NC}"
    MAIN_PID=""
fi
cd ..

# 仅当所有服务健康时才显示成功信息
if [ "$CONVERT_HEALTH_CHECK" = true ] && [ "$ARCHIVE_HEALTH_CHECK" = true ] && [ -n "$MAIN_PID" ]; then
    echo -e "${GREEN}所有服务已成功启动!${NC}"
echo -e "主应用: http://localhost:$MAIN_APP_PORT"
echo -e "转换服务: http://localhost:$CONVERT_SVC_PORT"
echo -e "归档服务: http://localhost:$ARCHIVE_SVC_PORT"
else
    echo -e "${RED}某些服务未正确启动，请检查日志${NC}"
fi

echo -e "${YELLOW}按 Ctrl+C 退出并关闭所有服务${NC}"

# 清理函数
function cleanup {
    echo -e "${YELLOW}正在关闭所有服务...${NC}"
    kill $CONVERT_PID $ARCHIVE_PID $MAIN_PID 2>/dev/null
    echo -e "${GREEN}所有服务已关闭${NC}"
    exit 0
}

# 捕获Ctrl+C
trap cleanup SIGINT SIGTERM

# 等待用户输入Ctrl+C
echo -e "${YELLOW}服务已启动，按 Ctrl+C 停止所有服务${NC}"
while true; do
    sleep 1
done 