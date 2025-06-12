#!/bin/bash
# 重启所有服务

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${YELLOW}开始重启所有服务...${NC}"

# 停止所有服务进程
echo -e "${YELLOW}停止当前运行的服务进程...${NC}"
pkill -f convert-svc
pkill -f archive-svc
pkill -f "python.*run.py"

sleep 2

# 启动主应用
echo -e "${YELLOW}启动主应用...${NC}"
cd 2025-05-14-16.25
# 使用虚拟环境
source venv/bin/activate
PYTHONPATH=. python run.py &
cd ..

sleep 2

# 重新构建并启动转换服务
echo -e "${YELLOW}重新构建转换服务...${NC}"
cd convert-svc
go build -o convert-svc ./cmd/main.go
chmod +x convert-svc

# 确保存储目录存在
echo -e "${YELLOW}确保转换服务存储目录存在...${NC}"
mkdir -p storage/uploads storage/converted storage/archive
chmod -R 755 storage

# 启动转换服务
echo -e "${YELLOW}启动转换服务...${NC}"
# 不提供端口参数，使用默认配置
./convert-svc &
cd ..

echo -e "${GREEN}服务已重启！${NC}"
echo -e "${YELLOW}请访问主应用: http://localhost:8001${NC}" 