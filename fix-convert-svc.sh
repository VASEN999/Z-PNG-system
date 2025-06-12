#!/bin/bash
# 此脚本修复转换服务的订单目录问题

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${YELLOW}开始修复转换服务...${NC}"

# 停止转换服务
echo -e "${YELLOW}查找并停止当前运行的转换服务进程...${NC}"
CONVERT_PID=$(ps aux | grep convert-svc | grep -v grep | awk '{print $2}')
if [ ! -z "$CONVERT_PID" ]; then
  echo -e "${YELLOW}发现转换服务进程: $CONVERT_PID，正在停止...${NC}"
  kill $CONVERT_PID
  sleep 2
else
  echo -e "${YELLOW}未找到运行中的转换服务进程${NC}"
fi

# 备份当前服务代码
echo -e "${YELLOW}备份当前代码...${NC}"
cd convert-svc
cp api/server.go api/server.go.backup

# 修改server.go中的代码
echo -e "${YELLOW}修改server.go代码...${NC}"

# 添加日志记录
sed -i 's/func (s \*Server) convertFile(c \*gin.Context) {/func (s \*Server) convertFile(c \*gin.Context) {\n\t\/\/ 打印请求参数\n\tfmt.Printf("收到转换请求 - 文件路径: %s, 订单ID: %s\\n", req.FilePath, req.OrderId)/g' api/server.go

# 重新构建服务
echo -e "${YELLOW}重新构建转换服务...${NC}"
go build -o convert-svc ./cmd/main.go
chmod +x convert-svc

# 清空已存在的文件
echo -e "${YELLOW}清空converted目录内的文件...${NC}"
rm -rf ./storage/converted/*
mkdir -p ./storage/converted

# 重启转换服务
echo -e "${YELLOW}重启转换服务...${NC}"
cd ..
./convert-svc/convert-svc &

# 等待服务启动
echo -e "${YELLOW}等待服务启动...${NC}"
sleep 3

# 测试订单子目录功能
echo -e "${YELLOW}测试订单子目录功能...${NC}"
python3 test-convert-svc.py

echo -e "${GREEN}修复完成！${NC}" 