# Archive-SVC

文件归档与哈希检索服务，一个高性能的文件存储和管理系统。

## 特性

- 基于FastAPI的异步API设计，高效处理并发请求
- 文件哈希计算和重复检测
- 文件版本控制
- 基于文件哈希的搜索和检索
- 分类和标签管理
- 文件元数据存储
- 软删除和恢复支持

## 技术栈

- **后端框架**: FastAPI
- **数据库**: SQLAlchemy (异步支持)
- **存储**: 本地文件系统
- **API文档**: Swagger UI / ReDoc
- **容器化**: Docker支持

## 快速开始

### 开发环境

1. 克隆仓库
```bash
git clone <repository-url>
cd archive-svc
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 运行服务
```bash
uvicorn app.main:app --reload
```

### 使用Docker

```bash
# 构建镜像
docker build -t archive-svc .

# 运行容器
docker run -p 8000:8000 -v $(pwd)/storage:/app/storage archive-svc
```

## API文档

启动服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 主要API端点

### 健康检查

```
GET /api/v1/health
GET /api/v1/health/db
```

### 文件管理

```
# 上传文件
POST /api/v1/archive/files

# 获取文件列表
GET /api/v1/archive/files

# 获取文件详情
GET /api/v1/archive/files/{file_id}

# 通过哈希获取文件
GET /api/v1/archive/files/hash/{hash_value}

# 更新文件信息
PUT /api/v1/archive/files/{file_id}

# 删除文件
DELETE /api/v1/archive/files/{file_id}

# 下载文件
GET /api/v1/archive/files/{file_id}/download
```

## 配置

主要配置选项在 `app/config.py` 文件中：

- 数据库连接配置
- 存储路径配置
- 哈希算法配置
- API前缀配置

## 与主系统集成

可以通过以下方式集成到主系统：

```python
import requests

def archive_file(file_path):
    """归档文件并获取其哈希值"""
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {'category': 'documents'}
        response = requests.post('http://localhost:8000/api/v1/archive/files', files=files, data=data)
        
    if response.status_code == 200:
        result = response.json()
        return {
            'success': result['success'],
            'file_id': result['file']['id'],
            'sha256_hash': result['file']['sha256_hash']
        }
    return {'success': False}

def get_file_by_hash(hash_value):
    """通过哈希值查找文件"""
    response = requests.get(f'http://localhost:8000/api/v1/archive/files/hash/{hash_value}')
    if response.status_code == 200:
        return response.json()['file']
    return None
```

## 许可证

MIT 