#!/usr/bin/env python3
import requests
import json
import os
import sys
import base64

# 设置转换服务URL
CONVERT_SVC_URL = "http://localhost:8081"

def create_test_image():
    """创建一个测试图片文件"""
    # 1x1像素的PNG图片的base64编码
    png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAADElEQVQImWP4//8/AAX+Av5e8BQ1AAAAAElFTkSuQmCC"
    
    # 解码base64并写入文件
    with open("test.png", "wb") as f:
        f.write(base64.b64decode(png_data))
    
    return os.path.abspath("test.png")

def test_convert_with_order_id():
    """测试带订单ID的文件转换"""
    # 创建一个测试图片文件
    test_file_path = create_test_image()
    print(f"创建测试图片: {test_file_path}")
    
    # 准备转换请求
    payload = {
        "file_path": test_file_path,
        "order_id": "TEST-ORDER-123"  # 测试订单ID
    }
    
    # 发送请求
    try:
        print(f"发送请求到 {CONVERT_SVC_URL}/api/convert")
        print(f"请求内容: {json.dumps(payload, ensure_ascii=False)}")
        response = requests.post(f"{CONVERT_SVC_URL}/api/convert", json=payload)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        # 检查输出目录结构
        print("\n检查输出目录结构:")
        os.system(f"find convert-svc/storage/converted -type d")
        
        # 如果成功，检查文件
        if response.status_code == 200:
            print("\n检查输出文件:")
            os.system(f"find convert-svc/storage/converted -type f")
        
    except Exception as e:
        print(f"请求失败: {str(e)}")

if __name__ == "__main__":
    test_convert_with_order_id() 