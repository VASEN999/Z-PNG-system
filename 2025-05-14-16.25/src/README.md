# 文件转换系统

这是一个基于Flask的文件转换系统，支持多种文件格式的转换和预览。

## 项目结构

```
src/
├── api/                   # 路由层
│   ├── __init__.py
│   ├── admin_routes.py    # 管理员相关路由
│   ├── mail_routes.py     # 邮件相关路由
│   ├── main_routes.py     # 主要功能路由
│   └── order_routes.py    # 订单相关路由
│
├── services/              # 业务逻辑层
│   ├── __init__.py
│   ├── admin_service.py   # 管理员业务逻辑
│   ├── file_service.py    # 文件处理业务逻辑
│   ├── mail_service.py    # 邮件业务逻辑
│   └── order_service.py   # 订单业务逻辑
│
├── repositories/          # 数据访问层
│   ├── __init__.py
│   ├── admin_repo.py      # 管理员数据访问
│   ├── file_repo.py       # 文件数据访问
│   ├── mail_repo.py       # 邮件数据访问
│   └── order_repo.py      # 订单数据访问
│
├── models/                # 数据模型
│   ├── __init__.py
│   └── models.py          # 所有模型定义
│
├── templates/             # 模板文件
│   ├── admin/             # 管理员模板
│   ├── mail/              # 邮件模板
│   ├── orders/            # 订单模板
│   ├── base.html
│   ├── index.html
│   └── ...
│
├── static/                # 静态资源
│   ├── css/
│   ├── js/
│   └── images/
│
├── utils/                 # 工具函数
│   ├── __init__.py
│   └── file_utils.py      # 文件处理工具函数
│
├── uploads/               # 上传文件存储目录
├── converted/             # 转换后文件存储目录
├── archive/               # 文件归档目录
├── flask_session/         # Flask会话存储目录
├── config.py              # 配置文件
├── app.py                 # 应用程序入口
└── run.py                 # 启动脚本
```

## 功能特性

- 支持多种文件格式的上传和转换
- 文件预览功能
- 用户管理和权限控制
- 订单管理
- 邮件接收和处理
- 文件存档和恢复

## 安装和配置

### 环境要求

- Python 3.8+
- Flask
- SQLAlchemy
- Pillow
- PyMuPDF
- python-docx
- python-pptx
- rarfile
- 其他依赖项（见requirements.txt）

### 安装步骤

1. 克隆仓库
```bash
git clone <repository-url>
cd <repository-directory>
```

2. 创建虚拟环境并激活
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量（可选）
```bash
export FLASK_APP=src/run.py
export FLASK_ENV=development
```

5. 初始化数据库
```bash
python -c "from src.app import create_app; from src.models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

6. 运行应用
```bash
python src/run.py
```

## 使用说明

1. 访问 `http://localhost:8080` 打开应用
2. 使用默认管理员账户登录（用户名: admin, 密码: admin123）
3. 上传文件并进行转换
4. 查看和管理订单

## 开发者指南

### 添加新的文件转换功能

1. 在 `src/utils/file_utils.py` 中添加新的转换函数
2. 在 `src/services/file_service.py` 中添加相应的服务方法
3. 在 `src/api/main_routes.py` 中添加路由处理函数

### 添加新的API端点

1. 在相应的路由文件（如 `src/api/main_routes.py`）中添加新的路由函数
2. 如果需要，在服务层和存储库层添加相应的方法

## 许可证

本项目采用MIT许可证。详见LICENSE文件。 