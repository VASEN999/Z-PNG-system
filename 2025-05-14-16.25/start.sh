#!/bin/bash
set -e

# 激活虚拟环境(如果存在)
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# 检查和安装依赖
if [ -f "requirements_simple.txt" ]; then
  echo "安装依赖..."
  pip install -r requirements_simple.txt
else
  echo "警告: 依赖文件不存在"
fi

# 创建必要目录
echo "创建必要目录..."
mkdir -p app/uploads app/converted app/archive flask_session

# 运行应用
echo "启动应用..."
python run.py
