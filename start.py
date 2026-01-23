#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能家装效果生成系统启动脚本
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
        'src', 'data/user', 'data/user_input', 
        'data/furniture', 'data/output', 
        'prompt_log', 'project_log'
    ]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            print(f"⚠️  创建目录: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
    
    print("✅ 目录结构检查完成")
    
    # 检查.env文件
    if not os.path.exists('.env'):
        print("⚠️  .env文件不存在，请配置环境变量")
        return False
    
    print("✅ 环境配置文件存在")
    return True

def install_dependencies():
    """安装依赖包"""
    print("\n检查Python依赖...")
    
    try:
        import flask
        import PIL
        import requests
        print("✅ 核心依赖已安装")
        return True
    except ImportError as e:
        print(f"⚠️  缺少依赖: {e}")
        print("正在安装依赖...")
        
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
            ])
            print("✅ 依赖安装完成")
            return True
        except subprocess.CalledProcessError:
            print("❌ 依赖安装失败")
            return False

def check_furniture_library():
    """检查家具库"""
    furniture_dir = Path('data/furniture')
    furniture_files = list(furniture_dir.glob('*.jpg')) + \
                     list(furniture_dir.glob('*.png')) + \
                     list(furniture_dir.glob('*.gif'))
    
    if len(furniture_files) == 0:
        print("⚠️  家具库为空，请在 data/furniture 目录中添加家具图片")
        print("   参考: data/furniture/README.md")
    else:
        print(f"✅ 家具库包含 {len(furniture_files)} 个文件")

def start_application():
    """启动应用"""
    print("\n启动智能家装效果生成系统...")
    print("=" * 50)
    
    # 切换到src目录
    os.chdir('src')
    
    # 启动Flask应用
    try:
        subprocess.run([sys.executable, 'app.py'])
    except KeyboardInterrupt:
        print("\n应用已停止")
    except Exception as e:
        print(f"启动失败: {e}")

def main():
    """主函数"""
    print("智能家装效果生成系统")
    print("=" * 50)
    
    # 检查环境
    if not check_environment():
        print("❌ 环境检查失败，请解决问题后重试")
        return
    
    # 安装依赖
    if not install_dependencies():
        print("❌ 依赖安装失败，请手动安装")
        return
    
    # 检查家具库
    check_furniture_library()
    
    # 启动应用
    print("\n🚀 准备启动应用...")
    print("应用将在 http://localhost:5000 运行")
    print("按 Ctrl+C 停止应用")
    
    input("\n按回车键继续...")
    start_application()

if __name__ == '__main__':
    main()