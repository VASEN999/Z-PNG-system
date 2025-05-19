# Ubuntu环境项目安装指南

本指南帮助你在Ubuntu系统上设置该Flask应用项目。

## 1. 系统依赖安装

项目需要一些系统级依赖，包括用于文件转换和图像处理的库：

```bash
# 更新包列表
sudo apt update

# 安装Python相关工具
sudo apt install -y python3-venv python3-dev build-essential

# 安装图像处理相关依赖
sudo apt install -y poppler-utils tesseract-ocr libtesseract-dev

# 安装文档处理相关依赖
sudo apt install -y libreoffice imagemagick ghostscript

# 安装PDF处理相关依赖
sudo apt install -y libmagickwand-dev libmupdf-dev
```

## 2. 解决ImageMagick策略限制

Ubuntu上的ImageMagick默认有安全限制，需要修改配置：

```bash
# 编辑ImageMagick策略文件
sudo nano /etc/ImageMagick-6/policy.xml
```

找到并注释掉或修改以下行（大约在文件末尾）：
```xml
<!-- <policy domain="coder" rights="none" pattern="PDF" /> -->
```

## 3. 项目设置

```bash
# 创建并激活Python虚拟环境
cd /home/vasen/桌面/2025-5-16-003/2025-05-14-16.25
python3 -m venv venv
source venv/bin/activate

# 安装项目依赖
pip install -r requirements_linux.txt

# 如遇到PyMuPDF安装问题，尝试：
pip install --upgrade pip
pip install PyMuPDF==1.22.5
```

## 4. 替换Windows特定路径

项目中包含了Windows风格路径，需要进行替换：

```bash
# 检查任何Windows样式路径引用
grep -r "C:\\\\" .
grep -r "\\\\Users" .
```

找到的任何Windows路径都需要替换为Linux风格路径。

## 5. 依赖替换

Windows特定依赖的替代方案：

1. **python-magic-bin**: 替换为Linux原生包
   ```bash
   pip uninstall python-magic-bin
   pip install python-magic
   ```

2. **pywin32**: 移除此依赖，它不适用于Linux
   ```bash
   # 从requirements.txt中移除，并确保代码不依赖此库
   ```

## 6. 初始化数据库

```bash
# 创建初始数据库
python run.py
```

## 7. 排查常见问题

### PDF转换问题

如果PDF转PNG失败：
```bash
# 确保ImageMagick有权限转换PDF
sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml
```

### 路径分隔符问题

如代码中有硬编码的Windows风格路径分隔符 `\`，需修改为 `/`：

```python
# Windows风格
path = "folder\\file.txt"

# 改为
import os
path = os.path.join("folder", "file.txt")
```

### 文件权限问题

确保应用有足够权限访问上传和转换目录：

```bash
# 设置适当权限
chmod -R 755 app/uploads app/converted app/archive
```

## 8. 启动应用

```bash
# 使用Flask内置服务器运行（开发环境）
python run.py

# 或使用Gunicorn（生产环境）
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## 9. 测试应用

访问 http://localhost:5000 检查应用是否正常工作。

如遇问题，请查看 `app.log` 文件获取详细错误信息。 