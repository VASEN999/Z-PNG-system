#!/bin/bash
# 环境设置与依赖安装脚本

echo "=== 开始设置应用环境 ==="

# 检查是否在虚拟环境中
if [[ "$VIRTUAL_ENV" == "" ]]; then
  echo "未检测到虚拟环境，将创建新的虚拟环境..."
  
  # 删除可能存在的旧虚拟环境
  if [ -d "venv" ]; then
    echo "删除旧的虚拟环境..."
    rm -rf venv
  fi
  
  # 创建新的虚拟环境
  echo "创建新的虚拟环境..."
  python3 -m venv venv
  
  # 激活虚拟环境
  echo "激活虚拟环境..."
  source venv/bin/activate
else
  echo "已在虚拟环境中: $VIRTUAL_ENV"
fi

# 更新pip
echo "更新pip..."
pip install --upgrade pip

# 安装必要依赖
echo "安装基本依赖..."
pip install -r requirements_simple.txt

# 确保安装了imap-tools
echo "确认安装imap-tools..."
pip install imap-tools

# 创建必要的目录
echo "创建必要的目录结构..."
mkdir -p app/uploads app/converted app/archive flask_session

# 设置权限
echo "设置目录权限..."
chmod -R 755 app/uploads app/converted app/archive flask_session

echo "=== 环境设置完成 ==="
echo "现在您可以运行应用: python run.py" 