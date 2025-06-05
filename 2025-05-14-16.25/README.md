# 文件转换系统

一个基于Flask的文件转换系统，可以将多种格式的文件转换为标准图片格式。

## 项目结构

```
2025-05-14-16.25/
├── app/                     # 旧版应用目录（已经迁移到src）
├── src/                     # 新版应用代码目录
│   ├── api/                 # 路由处理
│   ├── models/              # 数据模型
│   ├── repositories/        # 数据访问层
│   ├── services/            # 业务逻辑层
│   ├── utils/               # 工具函数
│   ├── app.py               # 应用创建和初始化
│   ├── config.py            # 旧版配置
│   ├── run.py               # 应用启动脚本（被项目根目录的run.py调用）
│   └── settings.py          # 新版配置系统
├── templates/               # HTML模板
├── flask_session/           # Flask会话存储
├── instance/                # 实例配置目录
├── app.log                  # 应用日志
└── run.py                   # 新的入口点脚本
```

## 项目重构

本项目最近完成了重构，从单体结构转变为分层架构：
- API层：处理HTTP请求和响应
- 服务层：包含业务逻辑
- 存储库层：负责数据访问
- 模型层：定义数据结构

## 启动应用

有两种方式可以启动应用：

1. 直接在项目目录下运行：
```bash
cd /home/vasen/桌面/2025-5-16-003/2025-05-14-16.25
python run.py
```

2. 从根目录启动（推荐）：
```bash
cd /home/vasen/桌面/2025-5-16-003
python run.py
```

## 功能特性

- 文件上传与转换
- 压缩包内文件处理
- 支持PDF、Word、PPT、图片等格式转换
- 用户登录与权限管理
- 订单与文件管理
- 邮件处理

## 开发环境配置

1. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

2. 安装依赖：
```bash
pip install -r src/requirements.txt
```

3. 运行开发服务器：
```bash
python run.py
```

## 默认用户

- 用户名：admin
- 密码：admin123 