#!/bin/bash
# 启动转换服务的脚本

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${YELLOW}文件转换服务启动脚本${NC}"
echo "------------------------------"

# 检查Go是否已安装
if ! command -v go &> /dev/null; then
    echo -e "${RED}错误: Go语言未安装!${NC}"
    echo "请安装Go (推荐1.21或更高版本):"
    echo "  Ubuntu/Debian: sudo apt install golang-go"
    echo "  其他系统请访问: https://golang.org/dl/"
    exit 1
fi

# 检查依赖
echo -e "${YELLOW}检查必要依赖...${NC}"
DEPS_MISSING=0

check_dep() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}未找到: $1${NC}"
        DEPS_MISSING=1
    else
        echo -e "${GREEN}已安装: $1${NC}"
    fi
}

# 检查PDF转换工具
check_dep "pdftoppm"
# 检查Office转换工具
check_dep "libreoffice"
# 检查图片转换工具
check_dep "convert"

# 如果有依赖缺失，显示安装指令
if [ $DEPS_MISSING -eq 1 ]; then
    echo -e "\n${RED}有必要的依赖未安装!${NC}"
    echo "请运行以下命令安装所需依赖:"
    echo -e "${YELLOW}sudo apt-get update && sudo apt-get install -y poppler-utils libreoffice imagemagick fonts-noto-cjk${NC}"
    read -p "是否现在安装这些依赖? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt-get update && sudo apt-get install -y poppler-utils libreoffice imagemagick fonts-noto-cjk
    else
        echo -e "${RED}依赖未安装，服务可能无法正常运行${NC}"
    fi
fi

# 切换到转换服务目录
cd "$(dirname "$0")/convert-svc" || exit 1

echo -e "\n${YELLOW}开始构建转换服务...${NC}"
# 下载Go依赖
go mod tidy || exit 1
# 构建应用
go build -o convert-svc ./cmd/main.go || exit 1

# 创建存储目录
mkdir -p storage/{uploads,converted,archive}

echo -e "\n${GREEN}构建成功!${NC}"
echo -e "${YELLOW}启动文件转换服务...${NC}"

# 启动服务
./convert-svc

# 退出处理
echo -e "\n${RED}服务已停止${NC}" 