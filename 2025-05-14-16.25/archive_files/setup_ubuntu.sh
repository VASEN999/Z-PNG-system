#!/bin/bash
# Ubuntu环境自动安装脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 日志函数
log_info() {
    echo -e "${BLUE}[信息]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

log_error() {
    echo -e "${RED}[错误]${NC} $1"
}

# 错误处理
set -e

log_info "开始设置Ubuntu环境..."

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then
    log_warn "此脚本需要使用sudo来安装系统级依赖"
    log_info "请输入密码以继续"
fi

# 更新包列表
log_info "更新包列表..."
sudo apt update

# 安装系统依赖
log_info "安装系统依赖..."
sudo apt install -y python3-venv python3-dev build-essential \
                   poppler-utils tesseract-ocr libtesseract-dev \
                   libreoffice imagemagick ghostscript \
                   libmagickwand-dev libmupdf-dev

# 设置ImageMagick策略
log_info "配置ImageMagick策略..."
if [ -f /etc/ImageMagick-6/policy.xml ]; then
    # 备份原始策略文件
    sudo cp /etc/ImageMagick-6/policy.xml /etc/ImageMagick-6/policy.xml.bak
    
    # 修改PDF权限策略
    sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml
    log_success "ImageMagick已配置，允许PDF处理"
else
    log_warn "未找到ImageMagick策略文件，可能需要手动配置"
fi

# 创建虚拟环境
log_info "创建Python虚拟环境..."
CURRENT_DIR=$(pwd)

if [ -d venv ]; then
    log_warn "虚拟环境已存在，将被重建"
    rm -rf venv
fi

python3 -m venv venv
source venv/bin/activate

# 安装依赖
log_info "安装Python依赖..."
pip install --upgrade pip

# 如果存在Linux专用requirements文件，使用它
if [ -f requirements_linux.txt ]; then
    pip install -r requirements_linux.txt
else
    log_warn "未找到requirements_linux.txt，尝试使用原始requirements.txt"
    pip install -r requirements.txt || {
        log_error "安装依赖失败，请查看错误信息"
        exit 1
    }
fi

# 处理Windows特定依赖
log_info "替换Windows特定依赖..."
pip uninstall -y python-magic-bin || true
pip install python-magic

# 检查Windows路径问题
log_info "检查Windows路径问题..."
python fix_windows_paths.py

# 创建所需目录
log_info "创建必要的目录..."
mkdir -p app/uploads app/converted app/archive/uploads app/archive/converted flask_session
chmod -R 755 app/uploads app/converted app/archive

# 创建数据库
log_info "初始化数据库..."
export RESET_DB=true
python run.py &
PID=$!

# 等待5秒后终止进程
sleep 5
kill $PID || true

# 完成
log_success "==============================================="
log_success "安装完成！"
log_success "使用以下命令启动应用："
log_success "source venv/bin/activate"
log_success "python run.py"
log_success "然后访问 http://localhost:5000"
log_success "===============================================" 