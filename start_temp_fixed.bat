@echo off
echo ========================================
echo AI装修应用 - 临时测试模式（固定结果）
echo ========================================
echo.
echo 使用固定的豆包API结果进行测试
echo 不会产生新的API调用费用
echo 端口: 5002
echo.
echo 按任意键启动...
pause
echo.
echo 启动中...
cd /d "%~dp0"
python src/app_temp_fixed.py
pause