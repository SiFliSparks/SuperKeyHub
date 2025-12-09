#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import platform
import importlib
import requests
import zipfile
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class Colors:
    """控制台颜色输出"""
    if platform.system() == "Windows":
        try:
            import colorama
            colorama.init()
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            MAGENTA = '\033[95m'
            CYAN = '\033[96m'
            WHITE = '\033[97m'
            RESET = '\033[0m'
            BOLD = '\033[1m'
        except ImportError:
            RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = RESET = BOLD = ''
    else:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        BLUE = '\033[94m'
        MAGENTA = '\033[95m'
        CYAN = '\033[96m'
        WHITE = '\033[97m'
        RESET = '\033[0m'
        BOLD = '\033[1m'

class LHMDownloader:
    """LibreHardwareMonitor DLL下载"""
    
    def __init__(self):
        self.github_api = "https://api.github.com/repos/LibreHardwareMonitor/LibreHardwareMonitor/releases/latest"
        self.fallback_releases = "https://api.github.com/repos/LibreHardwareMonitor/LibreHardwareMonitor/releases"
        self.libs_dir = Path("libs")
        self.dll_name = "LibreHardwareMonitorLib.dll"
        self.dll_path = self.libs_dir / self.dll_name
        self.expected_size_range = (500000, 3000000)  # 500KB - 3MB
    
    def ensure_libs_dir(self):
        """确保libs目录存在"""
        self.libs_dir.mkdir(exist_ok=True)
        print_status(f"创建/确认libs目录: {self.libs_dir.absolute()}")
    
    def check_existing_dll(self) -> bool:
        """检查是否已有有效的DLL文件"""
        if not self.dll_path.exists():
            return False
        
        try:
            size = self.dll_path.stat().st_size
            if self.expected_size_range[0] <= size <= self.expected_size_range[1]:
                print_status(f"发现有效的{self.dll_name} ({size//1024}KB)", "SUCCESS")
                return True
            else:
                print_status(f"{self.dll_name}文件大小异常 ({size}字节)，将重新下载", "WARNING")
                return False
        except Exception as e:
            print_status(f"检查{self.dll_name}时出错: {e}", "WARNING")
            return False
    
    def get_release_info(self, use_latest=True) -> Optional[dict]:
        """获取发布版本信息"""
        try:
            url = self.github_api if use_latest else self.fallback_releases
            print_status("正在获取LibreHardwareMonitor版本信息...")
            
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            if use_latest:
                return response.json()
            else:
                releases = response.json()
                for release in releases:
                    if not release.get('prerelease', False):
                        return release
                return releases[0] if releases else None
                
        except Exception as e:
            print_status(f"获取版本信息失败: {e}", "ERROR")
            return None
    
    def find_dll_asset(self, release_info: dict) -> Optional[dict]:
        """从发布信息中找到包含DLL的资源"""
        assets = release_info.get('assets', [])
        for asset in assets:
            name = asset['name'].lower()
            if ('net' in name or 'framework' in name) and name.endswith('.zip'):
                return asset
        for asset in assets:
            name = asset['name'].lower()
            if name.endswith('.zip') and 'source' not in name:
                return asset
        
        return None
    
    def download_and_extract_dll(self, asset: dict, version: str) -> bool:
        """下载并解压DLL文件"""
        try:
            download_url = asset['browser_download_url']
            file_size = asset.get('size', 0)
            asset_name = asset['name']
            
            print_status(f"正在下载 {asset_name} ({file_size//1024//1024}MB)...")
            response = requests.get(download_url, timeout=60, stream=True)
            response.raise_for_status()
            
            zip_path = self.libs_dir / f"lhm_{version}.zip"
            downloaded = 0
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if file_size > 0:
                            progress = (downloaded / file_size) * 100
                            print(f"\r下载进度: {progress:.1f}%", end='', flush=True)
            
            print() 
            print_status("下载完成，正在解压...")
            dll_found = False
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    file_path = Path(file_info.filename)
                    if file_path.name == self.dll_name:
                        print_status(f"找到DLL文件: {file_info.filename}")
                        with zip_ref.open(file_info) as source:
                            with open(self.dll_path, 'wb') as target:
                                target.write(source.read())
                        
                        dll_found = True
                        break
            try:
                zip_path.unlink()
            except:
                pass
            
            if not dll_found:
                print_status(f"在{asset_name}中未找到{self.dll_name}", "ERROR")
                return False
            if self.check_existing_dll():
                print_status(f"✓ {self.dll_name} 下载并验证成功", "SUCCESS")
                return True
            else:
                print_status(f"下载的{self.dll_name}验证失败", "ERROR")
                return False
            
        except Exception as e:
            print_status(f"下载过程中出错: {e}", "ERROR")
            return False
    
    def download_dll(self, force: bool = False) -> bool:
        """主下载函数"""
        self.ensure_libs_dir()
        if not force and self.check_existing_dll():
            return True
        release_info = self.get_release_info(use_latest=True)
        if not release_info:
            print_status("尝试获取稳定版本信息...", "WARNING")
            release_info = self.get_release_info(use_latest=False)
        
        if not release_info:
            print_status("无法获取版本信息", "ERROR")
            return False
        
        version = release_info.get('tag_name', 'unknown').lstrip('v')
        print_status(f"找到版本: {version}")
        asset = self.find_dll_asset(release_info)
        if not asset:
            print_status("未找到合适的下载文件", "ERROR")
            return False
        return self.download_and_extract_dll(asset, version)
    
    def manual_download_instructions(self):
        """显示手动下载说明"""
        print_status("自动下载失败，请手动下载:", "ERROR")
        print("  1. 访问: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases")
        print("  2. 下载最新版本的 .NET Framework 包")
        print("  3. 解压后找到 LibreHardwareMonitorLib.dll")
        print(f"  4. 将文件放入: {self.libs_dir.absolute()}")
        print("  5. 重新运行此脚本验证安装")

def print_header():
    """打印脚本标题"""
    print(f"{Colors.CYAN}{Colors.BOLD}")
    print("=" * 60)
    print("  WinSysHub项目 - 依赖安装器")
    print("  Dependencies Installer for WinSysHub")
    print("=" * 60)
    print(f"{Colors.RESET}")

def print_status(message: str, status: str = "INFO"):
    """打印状态信息"""
    color_map = {
        "INFO": Colors.BLUE,
        "SUCCESS": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "SKIP": Colors.MAGENTA
    }
    color = color_map.get(status, Colors.WHITE)
    print(f"{color}[{status:^7}]{Colors.RESET} {message}")

def check_python_version() -> bool:
    """检查Python版本"""
    min_version = (3, 7)
    current_version = sys.version_info[:2]
    
    print_status(f"检查Python版本: {sys.version.split()[0]}")
    
    if current_version >= min_version:
        print_status(f"Python版本满足要求 (>= {min_version[0]}.{min_version[1]})", "SUCCESS")
        return True
    else:
        print_status(f"Python版本过低! 需要 >= {min_version[0]}.{min_version[1]}", "ERROR")
        return False

def check_pip():
    """检查并确保pip可用"""
    try:
        import pip
        print_status("pip已可用", "SUCCESS")
        return True
    except ImportError:
        print_status("pip未安装，尝试安装...", "WARNING")
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
            print_status("pip安装成功", "SUCCESS")
            return True
        except subprocess.CalledProcessError:
            print_status("pip安装失败，请手动安装pip", "ERROR")
            return False

def get_pip_command() -> List[str]:
    """获取pip命令"""
    possible_commands = [
        [sys.executable, "-m", "pip"],
        ["pip3"],
        ["pip"]
    ]
    
    for cmd in possible_commands:
        try:
            result = subprocess.run(cmd + ["--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    return [sys.executable, "-m", "pip"] 

def is_module_installed(module_name: str) -> Tuple[bool, Optional[str]]:
    """检查模块是否已安装"""
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, '__version__', None)
        return True, version
    except ImportError:
        return False, None

def install_package(package_name: str, pip_cmd: List[str], is_optional: bool = False) -> bool:
    """安装Python包"""
    try:
        print_status(f"正在安装 {package_name}...")
        cmd = pip_cmd + ["install", package_name, "--upgrade"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print_status(f"{package_name} 安装成功", "SUCCESS")
            return True
        else:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            if is_optional:
                print_status(f"{package_name} 安装失败 (可选组件): {error_msg}", "WARNING")
            else:
                print_status(f"{package_name} 安装失败: {error_msg}", "ERROR")
            return False
            
    except subprocess.TimeoutExpired:
        print_status(f"{package_name} 安装超时", "ERROR" if not is_optional else "WARNING")
        return False
    except Exception as e:
        print_status(f"{package_name} 安装出错: {str(e)}", "ERROR" if not is_optional else "WARNING")
        return False

def download_lhm_dll(force: bool = False) -> bool:
    """下载LibreHardwareMonitor DLL"""
    downloader = LHMDownloader()
    
    try:
        success = downloader.download_dll(force=force)
        if not success:
            downloader.manual_download_instructions()
        return success
    except Exception as e:
        print_status(f"下载LibreHardwareMonitor DLL时出错: {e}", "ERROR")
        downloader.manual_download_instructions()
        return False

def check_special_dependencies():
    """检查特殊依赖"""
    print(f"\n{Colors.YELLOW}检查特殊依赖和平台兼容性:{Colors.RESET}")
    system = platform.system()
    print_status(f"操作系统: {system}")
    if system == "Windows":
        installed, version = is_module_installed("wmi")
        if installed:
            print_status(f"WMI支持已可用 (版本: {version or '未知'})", "SUCCESS")
        else:
            print_status("WMI支持不可用，某些硬件信息可能无法获取", "WARNING")
    else:
        print_status("非Windows系统，WMI不可用", "SKIP")
    try:
        import pynvml
        pynvml.nvmlInit()
        gpu_count = pynvml.nvmlDeviceGetCount()
        print_status(f"NVIDIA GPU支持已可用，检测到 {gpu_count} 个GPU", "SUCCESS")
    except:
        print_status("NVIDIA GPU支持不可用", "WARNING")
    try:
        import clr
        print_status(".NET互操作支持已可用", "SUCCESS")
    except:
        print_status(".NET互操作支持不可用，某些硬件监控功能可能受限", "WARNING")
    dll_path = Path("libs") / "LibreHardwareMonitorLib.dll"
    if dll_path.exists():
        size = dll_path.stat().st_size
        print_status(f"LibreHardwareMonitorLib.dll 已存在 ({size//1024}KB)", "SUCCESS")
    else:
        print_status("LibreHardwareMonitorLib.dll 不存在", "WARNING")

def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(
        description='WinSysHub 依赖安装器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python setup_dependencies.py          # 安装运行时依赖
  python setup_dependencies.py --dev    # 安装运行时 + 开发依赖
  python setup_dependencies.py --build-only  # 仅安装构建工具
        """
    )
    parser.add_argument('--dev', action='store_true', 
                       help='安装开发依赖（包含构建工具PyInstaller）')
    parser.add_argument('--build-only', action='store_true', 
                       help='仅安装构建工具，跳过其他依赖')
    parser.add_argument('--force-dll', action='store_true',
                       help='强制重新下载LibreHardwareMonitor DLL')
    args = parser.parse_args()
    
    print_header()

    if args.build_only:
        print_status("运行模式: 仅安装构建工具", "INFO")
    elif args.dev:
        print_status("运行模式: 开发者模式（完整安装）", "INFO")
    else:
        print_status("运行模式: 普通用户模式", "INFO")

    if not check_python_version():
        print_status("Python版本不满足要求，程序退出", "ERROR")
        sys.exit(1)

    if not check_pip():
        print_status("pip不可用，无法继续安装", "ERROR")
        sys.exit(1)
    pip_cmd = get_pip_command()
    print_status(f"使用pip命令: {' '.join(pip_cmd)}")

    required_packages = {
        'flet': 'flet',
        'psutil': 'psutil', 
        'pyserial': 'serial',
        'requests': 'requests',
        'pystray': 'pystray',  
        'Pillow': 'PIL',      
    }
    
    optional_packages = {
        'wmi': 'wmi',
        'pynvml': 'pynvml',
        'pythonnet': 'clr',
        'colorama': 'colorama'  
    }

    dev_packages = {
        'pyinstaller': 'PyInstaller'
    }
    
    failed_required = []

    if not args.build_only:
        print(f"\n{Colors.GREEN}检查必需依赖:{Colors.RESET}")

        for package_name, import_name in required_packages.items():
            installed, version = is_module_installed(import_name)
            
            if installed:
                print_status(f"{package_name} 已安装 (版本: {version or '未知'})", "SUCCESS")
            else:
                print_status(f"{package_name} 未安装，开始安装...")
                if install_package(package_name, pip_cmd, is_optional=False):
                    installed, version = is_module_installed(import_name)
                    if installed:
                        print_status(f"{package_name} 验证成功 (版本: {version or '未知'})", "SUCCESS")
                    else:
                        failed_required.append(package_name)
                else:
                    failed_required.append(package_name)
        
        print(f"\n{Colors.YELLOW}检查可选依赖:{Colors.RESET}")

        for package_name, import_name in optional_packages.items():
            installed, version = is_module_installed(import_name)
            
            if installed:
                print_status(f"{package_name} 已安装 (版本: {version or '未知'})", "SUCCESS")
            else:
                if package_name == 'wmi' and platform.system() != "Windows":
                    print_status(f"{package_name} 跳过 (非Windows系统)", "SKIP")
                    continue
                
                print_status(f"{package_name} 未安装，尝试安装...")
                install_package(package_name, pip_cmd, is_optional=True)

    if args.dev or args.build_only:
        print(f"\n{Colors.MAGENTA}检查开发/构建依赖:{Colors.RESET}")
        
        for package_name, import_name in dev_packages.items():
            installed, version = is_module_installed(import_name)
            
            if installed:
                print_status(f"{package_name} 已安装 (版本: {version or '未知'})", "SUCCESS")
            else:
                print_status(f"{package_name} 未安装，开始安装...")
                package_spec = f"{package_name}>=5.13.0"
                if install_package(package_spec, pip_cmd, is_optional=False):
                    installed, version = is_module_installed(import_name)
                    if installed:
                        print_status(f"{package_name} 验证成功 (版本: {version or '未知'})", "SUCCESS")
                    else:
                        failed_required.append(package_name)
                else:
                    failed_required.append(package_name)
    if not args.build_only:
        print(f"\n{Colors.BLUE}下载必需的第三方组件:{Colors.RESET}")
        
        lhm_success = download_lhm_dll(force=args.force_dll)
        if lhm_success:
            print_status("LibreHardwareMonitorLib.dll 下载成功", "SUCCESS")
        else:
            print_status("LibreHardwareMonitorLib.dll 下载失败", "ERROR")
            failed_required.append("LibreHardwareMonitorLib.dll")

    if not args.build_only:
        check_special_dependencies()

    print(f"\n{Colors.CYAN}{Colors.BOLD}安装总结:{Colors.RESET}")
    
    if args.build_only:
        if not failed_required:
            print_status("构建工具安装完成!", "SUCCESS")
            print_status("现在可以使用以下命令构建EXE:", "SUCCESS")
            print(f"  python build.py --all")
        else:
            print_status(f"构建工具安装失败: {', '.join(failed_required)}", "ERROR")
    elif args.dev:
        if not failed_required:
            print_status("所有依赖（运行时+开发）安装完成!", "SUCCESS")
            print_status("项目可以正常运行和构建", "SUCCESS")
            print(f"\n{Colors.GREEN}可用命令:{Colors.RESET}")
            print(f"  python main.py           # 运行程序")
            print(f"  python build.py --all    # 构建EXE文件")
        else:
            print_status(f"以下依赖安装失败: {', '.join(failed_required)}", "ERROR")
    else:
        if not failed_required:
            print_status("所有必需依赖安装完成!", "SUCCESS")
            print_status("项目可以正常运行", "SUCCESS")
            print(f"\n{Colors.GREEN}现在可以运行以下命令启动程序:{Colors.RESET}")
            print(f"  python main.py")
            print(f"\n{Colors.BLUE}如需构建EXE文件，请运行:{Colors.RESET}")
            print(f"  python setup_dependencies.py --dev")
            print(f"  python build.py --all")
        else:
            print_status(f"以下必需依赖安装失败: {', '.join(failed_required)}", "ERROR")
            print_status("请手动安装这些依赖或检查网络连接", "ERROR")
    if not args.build_only:
        print(f"\n{Colors.BLUE}生成requirements.txt文件...{Colors.RESET}")
        try:
            with open('requirements.txt', 'w', encoding='utf-8') as f:
                f.write("# WinSysHub 项目依赖\n")
                f.write("# WinSysHub Project Dependencies\n\n")
                
                f.write("# 必需依赖 / Required Dependencies\n")
                for package in required_packages.keys():
                    f.write(f"{package}\n")
                
                f.write("\n# 可选依赖 / Optional Dependencies\n")
                for package in optional_packages.keys():
                    f.write(f"# {package}\n")
                
                if args.dev:
                    f.write("\n# 开发/构建依赖 / Development/Build Dependencies\n")
                    for package in dev_packages.keys():
                        f.write(f"# {package}>=5.13.0\n")
                
                f.write("\n# 注意 / Notes:\n")
                f.write("# - LibreHardwareMonitorLib.dll 会自动下载\n")
                f.write("# - LibreHardwareMonitorLib.dll will be downloaded automatically\n")
                f.write("# - 开发依赖需要 --dev 参数安装\n")
                f.write("# - Development dependencies require --dev flag\n")
            print_status("requirements.txt 生成成功", "SUCCESS")
        except Exception as e:
            print_status(f"requirements.txt 生成失败: {e}", "WARNING")
    if args.dev or args.build_only:
        print(f"\n{Colors.BLUE}生成build_requirements.txt文件...{Colors.RESET}")
        try:
            with open('build_requirements.txt', 'w', encoding='utf-8') as f:
                f.write("# WinSysHub 构建依赖\n")
                f.write("# WinSysHub Build Dependencies\n\n")
                for package in dev_packages.keys():
                    f.write(f"{package}>=5.13.0\n")
            print_status("build_requirements.txt 生成成功", "SUCCESS")
        except Exception as e:
            print_status(f"build_requirements.txt 生成失败: {e}", "WARNING")
    
    print(f"\n{Colors.MAGENTA}额外说明:{Colors.RESET}")
    if args.build_only:
        print("• 构建工具已安装，现在可以构建EXE文件")
        print("• 使用 python build.py --all 开始构建")
    elif args.dev:
        print("• 开发环境已完整配置")
        print("• LibreHardwareMonitorLib.dll 已自动下载")
        print("• 可以运行程序或构建EXE文件")
        print("• 某些功能需要管理员权限")
    else:
        print("• LibreHardwareMonitorLib.dll 已自动下载 (如果下载失败请手动获取)")
        print("• 在Windows上运行效果最佳")
        print("• 某些功能需要管理员权限")
        print("• 如需配置API服务，请参考程序内设置页面")
        print("• 如需构建EXE，请使用 --dev 参数重新运行此脚本")
    
    if failed_required:
        print(f"\n{Colors.RED}由于必需依赖安装失败，程序可能无法正常运行{Colors.RESET}")
        sys.exit(1)
    else:
        if args.build_only:
            print(f"\n{Colors.GREEN}构建工具安装完成! 现在可以构建EXE文件了{Colors.RESET}")
        elif args.dev:
            print(f"\n{Colors.GREEN}开发环境安装完成! 现在可以运行程序或构建EXE了{Colors.RESET}")
        else:
            print(f"\n{Colors.GREEN}安装完成! 现在可以运行主程序了{Colors.RESET}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}用户中断安装{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}安装过程中出现错误: {e}{Colors.RESET}")
        sys.exit(1)