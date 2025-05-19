#!/usr/bin/env python3
"""检查未使用的数据库模型"""
import os
import re

def get_all_model_classes():
    """从models.py中提取所有模型类名"""
    with open('models.py', 'r') as f:
        content = f.read()
    
    # 查找模型类定义
    model_pattern = r'class\s+(\w+)\s*\(\s*db\.Model'
    return re.findall(model_pattern, content)

def find_model_usage(model_name):
    """在项目文件中搜索模型名称的使用"""
    count = 0
    for root, _, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    content = f.read()
                    # 计算模型名称出现的次数
                    count += content.count(model_name)
    return count

def main():
    models = get_all_model_classes()
    print(f"在models.py中找到{len(models)}个模型类")
    
    for model in models:
        usage_count = find_model_usage(model)
        if usage_count == 0:
            print(f"警告: 模型'{model}'在应用代码中未被使用")
        else:
            print(f"模型'{model}'在应用中被使用了{usage_count}次")

if __name__ == '__main__':
    main() 