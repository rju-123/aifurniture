#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速修复测试脚本
"""

import os
import sys
import time
import requests
import subprocess
import threading

def check_furniture_files():
    """检查家具文件"""
    furniture_dir = "data/furniture"
    print(f"检查家具目录: {furniture_dir}")
    
    if os.path.exists(furniture_dir):
        files = os.listdir(furniture_dir)
        image_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
        print(f"找到图片文件: {image_files}")
        return len(image_files) > 0
    else:
        print("家具目录不存在!")
        return False

def test_furniture_api():
    """测试家具API"""
    print("\n测试家具API...")
    
    try:
        # 等待服务器启动
        time.sleep(2)
        
        response = requests.get('http://localhost:5000/furniture', timeout=5)
        print(f"API响应状态: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            furniture_list = data.get('furniture', [])
            print(f"API返回 {len(furniture_list)} 个家具项")
            
            for item in furniture_list:
                print(f"  - {item['name']}: {item['path']}")
            
            return len(furniture_list) > 0
        else:
            print(f"API错误: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("无法连接到服务器")
        return False
    except Exception as e:
        print(f"测试失败: {e}")
        return False

def main():
    """主函数"""
    print("智能家装效果生成 - 快速修复测试")
    print("=" * 50)
    
    # 检查家具文件
    if not check_furniture_files():
        print("❌ 没有找到家具文件，请确保在 data/furniture 目录中有图片文件")
        return
    
    print("✅ 家具文件检查通过")
    
    # 测试API
    if test_furniture_api():
        print("✅ 家具API测试通过")
        print("\n🎉 修复成功！现在应该可以在网页中看到家具了")
        print("请刷新浏览器页面: http://localhost:5000")
    else:
        print("❌ 家具API测试失败")
        print("请检查:")
        print("1. 应用是否正在运行 (python src/app.py)")
        print("2. 家具文件是否存在于 data/furniture 目录")
        print("3. 查看控制台输出的错误信息")

if __name__ == '__main__':
    main()