#!/usr/bin/env python3
"""检查并优化配置文件"""
import re
import os
import sys

def analyze_config():
    """分析配置文件"""
    if not os.path.exists('config.py'):
        print("配置文件config.py不存在")
        return
    
    with open('config.py', 'r') as f:
        content = f.read()
    
    # 检查重复的配置选项
    config_pattern = r'([A-Z_]+)\s*='
    configs = re.findall(config_pattern, content)
    duplicates = [item for item in configs if configs.count(item) > 1]
    
    if duplicates:
        print("警告: 发现重复的配置选项:")
        for dup in set(duplicates):
            print(f"  - {dup}")
    
    # 检查未使用的配置
    app_files = []
    for root, _, files in os.walk('app'):
        for file in files:
            if file.endswith('.py'):
                app_files.append(os.path.join(root, file))
    
    app_content = ""
    for file in app_files:
        with open(file, 'r') as f:
            app_content += f.read()
    
    unused_configs = []
    for config in configs:
        # 检查配置是否在应用代码中使用
        pattern = r'config\s*[\.\[][\'\"]?' + config + r'[\'\"]?\]?'
        if not re.search(pattern, app_content):
            # 检查是否是常见的必要配置
            common_configs = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI', 'DEBUG']
            if config not in common_configs:
                unused_configs.append(config)
    
    if unused_configs:
        print("\n警告: 可能未使用的配置选项:")
        for config in unused_configs:
            print(f"  - {config}")

if __name__ == '__main__':
    analyze_config() 