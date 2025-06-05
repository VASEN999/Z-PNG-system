# 文件转换与管理系统

一个基于微服务架构的文件转换、归档和管理系统。

## 系统架构

本系统采用微服务架构，包含三个主要服务：

1. **主应用服务** - 基于Flask的Web应用，提供用户界面和主要业务逻辑
2. **文件转换服务(convert-svc)** - 基于Go的高性能文件转换服务
3. **文件归档服务(archive-svc)** - 基于FastAPI的异步文件归档与检索服务

## 主要功能

- 文件上传和管理
- 文件转换（PDF/Word/PPT/图片转PNG）
- 文件归档和哈希检索
- 文件版本控制
- 文件去重（基于哈希值）

## 快速开始

### 安装依赖

```bash
# 安装Python依赖
pip install -r 2025-05-14-16.25/src/requirements.txt
pip install -r archive-svc/requirements.txt

# 安装系统依赖
sudo apt-get update && sudo apt-get install -y poppler-utils libreoffice imagemagick
```

### 启动服务

使用集成启动脚本启动所有服务：

```bash
./start-all-services.sh
```

或者分别启动各个服务：

```bash
# 启动主应用
cd 2025-05-14-16.25
python src/run.py

# 启动转换服务
cd convert-svc
./start-convert-svc.sh

# 启动归档服务
cd archive-svc
./start-archive-svc.sh
```

## 技术栈

- **主应用**：Python + Flask
- **文件转换服务**：Go + Command line tools
- **文件归档服务**：Python + FastAPI + SQLAlchemy

## 文档

- [微服务架构说明](./convert-svc-说明.md)
- [主应用微服务升级说明](./2025-05-14-16.25/微服务升级说明.md)
- [文件转换服务文档](./convert-svc/README.md)
- [文件归档服务文档](./archive-svc/README.md)

## 性能优化

1. **文件转换**
   - 使用Go语言实现高性能文件转换
   - 并发处理多文件
   
2. **文件归档**
   - 异步I/O处理文件读写
   - 哈希索引加速文件查找
   - 文件去重节省存储空间

## 目录结构

```
/
├── 2025-05-14-16.25/ - 主应用
├── convert-svc/ - 文件转换微服务（Go）
├── archive-svc/ - 文件归档微服务（FastAPI）
├── 归档/ - 归档文件存储
├── start-all-services.sh - 集成启动脚本
└── README.md - 项目说明
```