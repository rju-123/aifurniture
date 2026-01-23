#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遮罩图生成工具启动脚本
"""

import os
import sys
import subprocess
from pathlib import Path

def check_environment():
    """检查运行环境"""
    print("检查运行环境...")
    
    # 检查Python版本
    if sys.version_info < (3, 10):
        print("❌ Python版本需要3.10或更高")
        return False
    
    print(f"✅ Python版本: {sys.version}")
    
    # 检查必要的目录
    required_dirs = [
        'data/user', 
        'data/furniture', 
        'data/mask_img',
        'project_log'
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            print(f"⚠️  创建目录: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
    
    print("✅ 目录结构检查完成")
    return True

def check_dependencies():
    """检查依赖包"""
    print("\n检查Python依赖...")
    
    try:
        import flask
        import PIL
        print("✅ 核心依赖已安装")
        return True
    except ImportError as e:
        print(f"⚠️  缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_furniture_library():
    """检查家具库"""
    furniture_dir = Path('data/furniture')
    furniture_files = list(furniture_dir.glob('*.jpg')) + \
                     list(furniture_dir.glob('*.png')) + \
                     list(furniture_dir.glob('*.gif'))
    
    if len(furniture_files) == 0:
        print("⚠️  家具库为空，请在 data/furniture 目录中添加家具图片")
    else:
        print(f"✅ 家具库包含 {len(furniture_files)} 个文件")

def start_application():
    """启动应用"""
    print("\n启动遮罩图生成工具...")
    print("=" * 50)
    
    # 启动Flask应用
    try:
        subprocess.run([sys.executable, 'mask_generator.py'])
    except KeyboardInterrupt:
        print("\n应用已停止")
    except Exception as e:
        print(f"启动失败: {e}")

def main():
    """主函数"""
    print("遮罩图生成工具")
    print("=" * 50)
    
    # 检查环境
    if not check_environment():
        print("❌ 环境检查失败，请解决问题后重试")
        return
    
    # 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败，请安装依赖")
        return
    
    # 检查家具库
    check_furniture_library()
    
    # 启动应用
    print("\n🚀 准备启动应用...")
    print("应用将在 http://localhost:5001 运行")
    print("按 Ctrl+C 停止应用")
    print("\n功能说明:")
    print("  - 上传客厅照片")
    print("  - 选择并拖拽家具到合适位置")
    print("  - 生成组合图（客厅+家具叠加）")
    print("  - 生成遮罩图（家具为白色，背景为黑色）")
    print("  - 生成的图片保存在 data/mask_img 目录")
    
    input("\n按回车键继续...")
    start_application()

if __name__ == '__main__':
    main()
