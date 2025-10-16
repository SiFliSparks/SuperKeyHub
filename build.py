#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import shutil

def main():
    print("=" * 60)
    print("SuperKey Flet 打包工具")
    print("=" * 60)
    
    # 检查资源文件
    print("\n检查资源文件...")
    required_files = [
        "assets/logo_484x74.png",
        "libs/LibreHardwareMonitorLib.dll"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ 缺少: {file_path}")
            sys.exit(1)
    
    has_icon = os.path.exists("assets/app.ico")
    if has_icon:
        print(f"✓ assets/app.ico")
    
    # 清理旧文件
    print("\n清理旧文件...")
    for d in ['build', 'dist', '__pycache__']:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  清理: {d}")
    
    if os.path.exists('SuperKeyHUB.spec'):
        os.remove('SuperKeyHUB.spec')
        print(f"  清理: SuperKeyHUB.spec")
    
    # 第一步：使用 flet pack 生成基本结构
    print("\n第一步：使用 flet pack 生成 spec 文件...")
    
    cmd = [
        "flet", "pack", "main.py",
        "--name", "SuperKeyHUB",
        "--add-data", "assets/logo_484x74.png;assets",
        "--add-data", "libs;libs",
    ]
    
    if has_icon:
        cmd.extend(["--icon", "assets/app.ico"])
    
    # 添加所有 hidden imports
    hidden_imports = [
        "pythonnet", "clr", "System",
        "psutil", "wmi",
        "requests", "requests.adapters", "urllib3",
        "serial", "serial.tools", "serial.tools.list_ports",
        "flet", "flet.core", "flet_core",
        "threading", "queue", "datetime", "enum",
    ]
    
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])
    
    print("命令:", " ".join(cmd))
    print()
    
    result = subprocess.run(cmd)
    
    # 显示结果
    print("\n" + "=" * 60)
    if result.returncode == 0:
        print("✓ 打包成功!")
        exe_path = "dist/SuperKeyHUB.exe"
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"文件位置: {os.path.abspath(exe_path)}")
            print(f"文件大小: {size:.1f} MB")
            print("\n⚠ 提示: 首次运行可能需要管理员权限(硬件监控功能)")
        print("=" * 60)
    else:
        print("✗ 打包失败")
        print("=" * 60)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()