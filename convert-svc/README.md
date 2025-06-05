# Convert-SVC

简单高效的文件转换服务，将各种文档格式转换为PNG图片。

## 主要特点

- 使用Go语言开发，性能优异
- 单一可执行文件，部署简单
- 支持多种文档格式转换（PDF, DOCX, PPTX, 图片等）
- 提供REST API接口，方便集成
- 支持批量转换
- Docker支持

## 支持的文件格式

- PDF文档 → PNG图片
- Word文档(DOCX, DOC) → PNG图片
- PowerPoint文档(PPTX, PPT) → PNG图片
- 图片文件(JPG, JPEG, PNG, GIF, BMP) → PNG图片

## 系统要求

为了完全支持所有转换功能，需要安装以下依赖：

- poppler-utils (PDF转换)
- libreoffice (Office文档转换)
- imagemagick (图片处理)

在Debian/Ubuntu系统上安装依赖：

```bash
sudo apt-get update && sudo apt-get install -y poppler-utils libreoffice imagemagick fonts-noto-cjk
```

## 构建与运行

### 本地构建

需要Go 1.21或更高版本。

```bash
# 下载依赖
go mod download

# 构建
go build -o convert-svc ./cmd/main.go

# 运行
./convert-svc
```

### 使用Docker

```bash
# 构建Docker镜像
docker build -t convert-svc .

# 运行容器
docker run -p 8080:8080 -v $(pwd)/storage:/app/storage convert-svc
```

## API使用

### 健康检查

```
GET /api/health
```

### 转换单个文件

```
POST /api/convert
```

请求体示例：

```json
{
  "file_path": "/path/to/document.pdf",
  "output_dir": "/optional/output/path",
  "dpi": 300
}
```

### 批量转换

```
POST /api/convert-batch
```

请求体示例：

```json
{
  "files": [
    {
      "file_path": "/path/to/document1.pdf",
      "dpi": 300
    },
    {
      "file_path": "/path/to/document2.docx"
    }
  ]
}
```

## 与Flask应用集成

在Flask应用中调用转换服务：

```python
import requests
import json

def convert_document(file_path):
    """调用转换服务将文档转换为PNG图片"""
    url = "http://localhost:8080/api/convert"
    payload = {
        "file_path": file_path
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json()
        if result["success"]:
            return result["files"]
    
    return None
```

## 配置

配置文件位于`config/config.yaml`，可以通过命令行参数`--config`指定其他配置文件路径。

配置示例：

```yaml
server:
  address: ":8080"
  mode: "debug"  # debug或release

storage:
  upload_dir: "storage/uploads"
  converted_dir: "storage/converted"
  archive_dir: "storage/archive"

conversion:
  dpi: 300  # 转换DPI
  delete_original: false  # 转换后是否删除原始文件
``` 