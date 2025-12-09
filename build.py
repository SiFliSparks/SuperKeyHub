#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperKey 跨平台打包工具
支持 Windows/macOS/Linux
"""
import subprocess
import sys
import os
import shutil
import platform

# 平台检测
SYSTEM = platform.system().lower()
IS_WINDOWS = SYSTEM == 'windows'
IS_MACOS = SYSTEM == 'darwin'
IS_LINUX = SYSTEM == 'linux'


def main():
    print("=" * 60)
    print("SuperKey Flet 跨平台打包工具")
    print(f"当前平台: {platform.system()} {platform.release()}")
    print("=" * 60)
    
    # 检查资源文件
    print("\n检查资源文件...")
    required_files = [
        "assets/logo_484x74.png",
    ]
    
    # Windows 特定资源
    if IS_WINDOWS:
        required_files.append("libs/LibreHardwareMonitorLib.dll")
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ 缺少: {file_path}")
            sys.exit(1)
    
    # 检查可选图标
    has_icon = False
    icon_path = None
    if IS_WINDOWS and os.path.exists("assets/app.ico"):
        has_icon = True
        icon_path = "assets/app.ico"
        print(f"✓ {icon_path}")
    elif IS_MACOS and os.path.exists("assets/app.icns"):
        has_icon = True
        icon_path = "assets/app.icns"
        print(f"✓ {icon_path}")
    elif os.path.exists("assets/app.png"):
        has_icon = True
        icon_path = "assets/app.png"
        print(f"✓ {icon_path}")
    
    # 检查必需的Python模块
    print("\n检查Python模块...")
    required_modules = [
        "main.py",
        "hw_monitor.py",
        "weather_api.py",
        "serial_assistant.py",
        "finsh_data_sender.py",
        "config_manager.py",
        "system_tray.py",
    ]
    
    for module in required_modules:
        if os.path.exists(module):
            print(f"✓ {module}")
        else:
            print(f"✗ 缺少: {module}")
            sys.exit(1)
    
    # 清理旧文件
    print("\n清理旧文件...")
    for d in ['build', 'dist', '__pycache__']:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  清理: {d}")
    
    if os.path.exists('SuperKeyHUB.spec'):
        os.remove('SuperKeyHUB.spec')
        print(f"  清理: SuperKeyHUB.spec")
    
    # 构建命令
    print("\n开始打包...")
    
    # 路径分隔符: Windows用分号，macOS/Linux用冒号
    sep = ';' if IS_WINDOWS else ':'
    
    # Windows: 创建 UAC 清单文件请求管理员权限
    manifest_path = None
    if IS_WINDOWS:
        manifest_path = "SuperKeyHUB.manifest"
        manifest_content = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity
    version="1.0.0.0"
    processorArchitecture="*"
    name="SuperKeyHUB"
    type="win32"
  />
  <description>SuperKey Hardware Monitor</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="requireAdministrator" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10/11 -->
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
    </application>
  </compatibility>
</assembly>
'''
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest_content)
        print(f"✓ 创建 UAC 清单文件: {manifest_path}")
    
    cmd = [
        "flet", "pack", "main.py",
        "--name", "SuperKeyHUB",
        "--add-data", f"assets/logo_484x74.png{sep}assets",
    ]
    
    # Windows: 添加 UAC 清单
    if IS_WINDOWS and manifest_path:
        cmd.extend(["--uac-admin"])
    
    # 添加图标资源文件到打包（用于托盘图标）
    if has_icon and icon_path:
        cmd.extend(["--add-data", f"{icon_path}{sep}assets"])
    
    # Windows: 添加LHM库
    if IS_WINDOWS:
        cmd.extend(["--add-data", f"libs{sep}libs"])
    
    if has_icon and icon_path:
        cmd.extend(["--icon", icon_path])
    
    # 添加所有 hidden imports
    hidden_imports = [
        # 核心依赖
        "psutil",
        "requests", "requests.adapters", "urllib3",
        "serial", "serial.tools", "serial.tools.list_ports",
        "flet", "flet.core", "flet_core",
        "threading", "queue", "datetime", "enum",
        # 配置管理
        "json", "pathlib",
        # 系统托盘
        "pystray",
        "PIL", "PIL.Image",
    ]
    
    # 平台特定导入
    if IS_WINDOWS:
        hidden_imports.extend([
            "pythonnet", "clr", "System",
            "wmi",
            "pystray._win32",
            "winreg",
            "ctypes", "ctypes.wintypes",
        ])
    elif IS_MACOS:
        hidden_imports.extend([
            "pystray._darwin",
            "subprocess",
        ])
    elif IS_LINUX:
        hidden_imports.extend([
            "pystray._xorg",
            "subprocess",
        ])
    
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])
    
    print("命令:", " ".join(cmd))
    print()
    
    result = subprocess.run(cmd)
    
    # 显示结果
    print("\n" + "=" * 60)
    if result.returncode == 0:
        print("✓ 打包成功!")
        
        # 清理临时文件
        if IS_WINDOWS and manifest_path and os.path.exists(manifest_path):
            os.remove(manifest_path)
        
        if IS_WINDOWS:
            exe_path = "dist/SuperKeyHUB.exe"
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"文件位置: {os.path.abspath(exe_path)}")
                print(f"文件大小: {size:.1f} MB")
                print("\n✓ 已启用 UAC 管理员权限请求")
                print("  • 双击运行时会自动弹出 UAC 提示")
                print("  • 开机自启动使用任务计划程序（自动以管理员身份运行）")
                print(f"\n配置文件位置: %APPDATA%\\SuperKey\\superkey_config.json")
        
        elif IS_MACOS:
            app_path = "dist/SuperKeyHUB.app"
            if os.path.exists(app_path):
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(app_path)
                    for filename in filenames
                )
                size = total_size / (1024 * 1024)
                print(f"应用位置: {os.path.abspath(app_path)}")
                print(f"应用大小: {size:.1f} MB")
                print("\n⚠ 提示: 某些传感器功能可能需要安装额外工具:")
                print("  brew install osx-cpu-temp")
                print(f"\n配置文件位置: ~/Library/Application Support/SuperKey/superkey_config.json")
        
        elif IS_LINUX:
            exe_path = "dist/SuperKeyHUB"
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"文件位置: {os.path.abspath(exe_path)}")
                print(f"文件大小: {size:.1f} MB")
                print("\n⚠ 提示: 某些传感器功能可能需要安装额外工具:")
                print("  sudo apt install lm-sensors  # CPU温度")
                print("  nvidia-smi                   # NVIDIA GPU")
                print("  rocm-smi                     # AMD GPU")
                print(f"\n配置文件位置: ~/.config/SuperKey/superkey_config.json")
        
        print("\n✓ 功能列表:")
        print("  • 天气API配置自动保存")
        print("  • 串口配置自动保存")
        print("  • 下次启动自动连接上次使用的串口")
        print("  • 最小化到系统托盘后台运行")
        print("  • 可选开机自启动")
        print("=" * 60)
    else:
        print("✗ 打包失败")
        print("=" * 60)
    
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()