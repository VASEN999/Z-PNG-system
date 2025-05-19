#!/usr/bin/env python3
"""更新README文件，反映当前项目结构"""
import os

def generate_project_structure():
    """生成项目结构描述"""
    structure = []
    structure.append("## 项目结构")
    structure.append("")
    structure.append("```")
    
    # 添加主要目录和文件
    structure.append("|- app/                    # 应用主目录")
    structure.append("|- templates/              # HTML模板")
    structure.append("|- migrations/             # 数据库迁移")
    structure.append("|- instance/               # 实例配置")
    structure.append("|- flask_session/          # 会话存储")
    structure.append("|- db_manage.py            # 数据库管理工具")
    structure.append("|- models.py               # 数据库模型")
    structure.append("|- config.py               # 配置文件")
    structure.append("|- run.py                  # 应用入口")
    structure.append("|- start.sh                # 启动脚本")
    structure.append("|- requirements_simple.txt # 项目依赖")
    
    structure.append("```")
    structure.append("")
    structure.append("## 使用说明")
    structure.append("")
    structure.append("1. 安装依赖: `pip install -r requirements_simple.txt`")
    structure.append("2. 启动应用: `./start.sh`")
    structure.append("3. 数据库管理:")
    structure.append("   - 重置数据库: `python db_manage.py reset`")
    structure.append("   - 创建表: `python db_manage.py create_tables`")
    structure.append("   - 重置管理员: `python db_manage.py reset_admin`")
    
    return "\n".join(structure)

def update_readme():
    """更新README.md文件"""
    if not os.path.exists('README.md'):
        print("README.md文件不存在")
        return
    
    with open('README.md', 'r') as f:
        content = f.read()
    
    # 查找项目结构部分
    structure_start = content.find("## 项目结构")
    if structure_start == -1:
        # 如果没有项目结构部分，在文件末尾添加
        with open('README.md', 'a') as f:
            f.write("\n\n" + generate_project_structure())
        print("在README.md末尾添加了项目结构部分")
    else:
        # 查找下一个二级标题
        next_section = content.find("##", structure_start + 1)
        if next_section == -1:
            next_section = len(content)
        
        # 替换项目结构部分
        new_content = content[:structure_start] + generate_project_structure() + content[next_section:]
        with open('README.md', 'w') as f:
            f.write(new_content)
        print("更新了README.md中的项目结构部分")

if __name__ == '__main__':
    update_readme() 