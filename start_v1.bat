@echo off
echo ================================
echo   AI智能家装系统 v1.0 启动脚本
echo ================================
echo.

echo 1. 激活conda环境...
call conda activate ai_decoration
if errorlevel 1 (
    echo 错误: 无法激活ai_decoration环境
    echo 请先创建环境: conda create -n ai_decoration python=3.9
    pause
    exit /b 1
)

echo 2. 检查依赖...
python -c "import flask, dashscope; print('依赖检查通过')" 2>nul
if errorlevel 1 (
    echo 正在安装依赖...
    pip install -r requirements.txt
    pip install dashscope>=1.23.8
)

echo 3. 启动应用...
cd src
python app.py

pause