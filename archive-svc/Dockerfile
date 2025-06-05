FROM python:3.10-slim

LABEL maintainer="Admin <admin@example.com>"
LABEL description="文件归档与哈希检索服务"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    STORAGE_DIR=/app/storage \
    ARCHIVE_DIR=/app/storage/archive \
    TEMP_DIR=/app/storage/temp

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建存储目录
RUN mkdir -p ${STORAGE_DIR} ${ARCHIVE_DIR} ${TEMP_DIR} \
    && chmod -R 755 ${STORAGE_DIR}

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 