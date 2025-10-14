@echo off
echo 安装SuperKeyHub硬件监控依赖包...

echo.
echo [1/4] 卸载可能冲突的包...
pip uninstall -y clr
pip uninstall -y pythonnet

echo.
echo [2/4] 安装pythonnet (用于LibreHardwareMonitor)...
pip install pythonnet

echo.
echo [3/4] 安装pynvml (用于NVIDIA GPU监控)...
pip install pynvml

echo.
echo [4/4] 安装其他依赖包...
pip install pywin32
pip install wmi

echo.
echo 依赖包安装完成！
echo.
echo 注意事项：
echo 1. 确保以管理员权限运行程序
echo 2. 下载LibreHardwareMonitorLib.dll到程序目录
echo 3. 如果有NVIDIA显卡，需要安装最新驱动
echo.
pause