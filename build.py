#!/usr/bin/env python3
"""
SuperKeyHUB 跨平台构建脚本
v2.0 - 支持macOS原生硬件传感器库编译

使用方法:
    uv run python build.py --help
    uv run python build.py --install      # 安装依赖
    uv run python build.py --dev          # 安装开发依赖
    uv run python build.py --run          # 运行应用
    uv run python build.py --lint         # 代码检查
    uv run python build.py --format       # 格式化代码
    uv run python build.py --type-check   # 类型检查
    uv run python build.py --all          # 完整构建
    uv run python build.py --build-native # 编译macOS原生库
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ============================================================================
# 配置
# ============================================================================
APP_NAME: str = "SuperKeyHUB"
APP_VERSION: str = "1.6.1"
APP_AUTHOR: str = "SuperKey Team"
APP_DESCRIPTION: str = "SuperKey Hardware Monitor"

SYSTEM: str = platform.system().lower()
IS_WINDOWS: bool = SYSTEM == "windows"
IS_MACOS: bool = SYSTEM == "darwin"
IS_LINUX: bool = SYSTEM == "linux"

PROJECT_ROOT: Path = Path(__file__).parent
BUILD_DIR: Path = PROJECT_ROOT / "build"
DIST_DIR: Path = PROJECT_ROOT / "dist"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
LIBS_DIR: Path = PROJECT_ROOT / "libs"
TOOLS_DIR: Path = PROJECT_ROOT / "tools"  # 新增: 工具目录
MACOS_NATIVE_DIR: Path = PROJECT_ROOT / "macos_native"


# ============================================================================
# 工具函数
# ============================================================================
def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = False,
    capture: bool = False
) -> int:
    """运行命令并返回退出码"""
    print(f">>> {' '.join(cmd)}")
    sys.stdout.flush()
    
    if capture:
        result = subprocess.run(
            cmd, 
            cwd=cwd, 
            capture_output=True, 
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    else:
        # 实时输出，不缓冲
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            stdout=None,  # 直接输出到控制台
            stderr=None,
        )
    
    if check and result.returncode != 0:
        sys.exit(result.returncode)
    return result.returncode


def ensure_dir(path: Path) -> None:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)


def print_header(msg: str) -> None:
    """打印带格式的标题"""
    print()
    print(f"{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}")
    print()


# ============================================================================
# macOS 原生库编译
# ============================================================================
def build_macos_native() -> bool:
    """编译macOS原生硬件传感器库"""
    if not IS_MACOS:
        print("[SKIP] macOS原生库仅在macOS上编译")
        return True
    
    print_header("[NATIVE] 编译macOS原生硬件传感器库")
    
    if not MACOS_NATIVE_DIR.exists():
        print("[FAIL] 未找到macos_native目录")
        return False
    
    # 检查Xcode命令行工具
    result = run_cmd(["xcode-select", "-p"])
    if result != 0:
        print("[WARN] 未安装Xcode命令行工具")
        print("   运行: xcode-select --install")
        return False
    
    # 编译
    result = run_cmd(["make", "clean"], cwd=MACOS_NATIVE_DIR)
    result = run_cmd(["make"], cwd=MACOS_NATIVE_DIR)
    
    if result != 0:
        print("[FAIL] 编译失败")
        return False
    
    # 部署到libs目录
    ensure_dir(LIBS_DIR)
    dylib_path = MACOS_NATIVE_DIR / "libmacos_sensors.dylib"
    if dylib_path.exists():
        shutil.copy2(dylib_path, LIBS_DIR / "libmacos_sensors.dylib")
        print(f"[OK] 已复制到 {LIBS_DIR}")
    
    print("[OK] macOS原生库编译成功")
    return True


def install_macos_native_system() -> bool:
    """安装macOS原生库到系统"""
    if not IS_MACOS:
        print("[SKIP] 仅macOS")
        return True
    
    print_header("[NATIVE] 安装macOS原生库到系统")
    
    result = run_cmd(["sudo", "make", "install"], cwd=MACOS_NATIVE_DIR)
    if result != 0:
        print("[FAIL] 安装失败")
        return False
    
    print("[OK] 安装成功")
    return True


# ============================================================================
# 依赖管理
# ============================================================================
def install_deps() -> int:
    """安装项目依赖"""
    print_header("[PKG] 安装项目依赖")
    if IS_WINDOWS:
        # Windows 需要安装 pythonnet 和 wmi 以获取完整硬件数据
        return run_cmd(["uv", "sync", "--extra", "windows"])
    return run_cmd(["uv", "sync"])


def install_dev_deps() -> int:
    """安装开发依赖"""
    print_header("[PKG] 安装开发依赖")
    if IS_WINDOWS:
        return run_cmd(["uv", "sync", "--extra", "windows", "--group", "dev"])
    return run_cmd(["uv", "sync", "--group", "dev"])


# ============================================================================
# 代码质量
# ============================================================================
def lint_code(fix: bool = False) -> bool:
    """运行 ruff lint 检查"""
    print_header("[CHECK] 运行 Ruff lint 检查")

    if fix:
        run_cmd(["uv", "run", "ruff", "check", "--fix", "."])

    result = run_cmd(["uv", "run", "ruff", "check", ".", "--select=E,F"])
    if result != 0:
        print("[FAIL] Lint 检查失败 (存在 error)")
        return False
    print("[OK] Lint 检查通过")
    return True


def lint_all() -> bool:
    """运行完整 lint 检查"""
    print_header("[CHECK] 运行完整 Ruff lint 检查")
    result = run_cmd(["uv", "run", "ruff", "check", "."])
    if result != 0:
        print("[WARN] Lint 检查发现问题")
        return False
    print("[OK] 完整 Lint 检查通过")
    return True


def format_code() -> None:
    """格式化代码"""
    print_header("[FMT] 格式化代码")
    run_cmd(["uv", "run", "ruff", "format", "."])
    run_cmd(["uv", "run", "ruff", "check", "--fix", "."])
    print("[OK] 代码格式化完成")


def type_check() -> bool:
    """运行 mypy 类型检查"""
    print_header("[TYPE] 运行 Mypy 类型检查")
    result = run_cmd([
        "uv", "run", "mypy", ".",
        "--ignore-missing-imports",
        "--no-error-summary"
    ])
    if result != 0:
        print("[WARN] 类型检查发现问题")
        return False
    print("[OK] 类型检查通过")
    return True


# ============================================================================
# 运行应用
# ============================================================================
def run_app(minimized: bool = False) -> int:
    """运行应用"""
    print_header("[RUN] 运行应用")
    cmd = ["uv", "run", "python", "main.py"]
    if minimized:
        cmd.append("--minimized")
    return run_cmd(cmd)


# ============================================================================
# 清理
# ============================================================================
def clean_build() -> None:
    """清理构建目录"""
    print_header("[CLEAN] 清理构建目录")

    dirs_to_clean = [
        BUILD_DIR,
        DIST_DIR,
        PROJECT_ROOT / "__pycache__",
        PROJECT_ROOT / ".mypy_cache",
        PROJECT_ROOT / ".ruff_cache",
    ]

    for d in dirs_to_clean:
        if d.exists():
            shutil.rmtree(d)
            print(f"  已删除: {d}")

    for f in PROJECT_ROOT.glob("*.spec"):
        f.unlink()
        print(f"  已删除: {f}")

    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)

    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        pyc.unlink()

    print("[OK] 清理完成")


# ============================================================================
# sftool 检查与准备
# ============================================================================
def check_sftool() -> Path | None:
    """检查 sftool 是否存在于 tools 目录
    
    Returns:
        sftool 路径，不存在返回 None
    """
    if IS_WINDOWS:
        sftool_path = TOOLS_DIR / "sftool.exe"
    else:
        sftool_path = TOOLS_DIR / "sftool"
    
    if sftool_path.exists():
        return sftool_path
    return None


def prepare_tools_dir() -> bool:
    """准备工具目录，检查 sftool 是否存在"""
    print_header("[TOOLS] 检查外部工具")
    
    sftool = check_sftool()
    if sftool:
        print(f"[OK] 找到 sftool: {sftool}")
        # macOS/Linux: 确保有执行权限
        if not IS_WINDOWS:
            os.chmod(sftool, 0o755)
        return True
    else:
        print("[WARN] 未找到 sftool")
        print(f"   请将 sftool 放置在: {TOOLS_DIR}/")
        if IS_WINDOWS:
            print("   Windows: tools/sftool.exe")
        else:
            print("   macOS/Linux: tools/sftool")
        return False


# ============================================================================
# PyInstaller 构建
# ============================================================================
def verify_windows_deps() -> bool:
    """验证Windows平台依赖是否已安装"""
    if not IS_WINDOWS:
        return True
    
    print("[CHECK] 验证 Windows 硬件监控依赖...")
    
    try:
        result = subprocess.run(
            ["uv", "run", "python", "-c", "import clr; import wmi; print('OK')"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and "OK" in result.stdout:
            print("[OK] pythonnet 和 wmi 已正确安装")
            return True
        else:
            print("[FAIL] 依赖检查失败:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"[FAIL] 依赖检查异常: {e}")
        return False


def build_pyinstaller() -> bool:
    """使用 PyInstaller 构建可执行文件"""
    print_header(f"[BUILD] 构建 {APP_NAME}")

    # 环境诊断
    print("[DEBUG] Python version:", sys.version)
    print("[DEBUG] Working directory:", os.getcwd())
    print("[DEBUG] PROJECT_ROOT:", PROJECT_ROOT)
    sys.stdout.flush()

    # Windows: 验证硬件监控依赖
    if IS_WINDOWS and not verify_windows_deps():
        print("[WARN] Windows 依赖未正确安装，尝试重新安装...")
        run_cmd(["uv", "sync", "--extra", "windows", "--group", "dev"])
        if not verify_windows_deps():
            print("[FAIL] 无法安装 Windows 依赖，构建可能不完整")
            print("   请手动运行: uv sync --extra windows --group dev")

    args: list[str] = [
        "uv", "run", "pyinstaller",
        "--name", APP_NAME,
        "--windowed",
        "--onedir",
        "--clean",
        "--noconfirm",
    ]

    # 图标
    if IS_WINDOWS:
        icon_path = ASSETS_DIR / "app.ico"
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])
    elif IS_MACOS:
        icon_path = ASSETS_DIR / "app.icns"
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])

    # 资源文件
    sep = ";" if IS_WINDOWS else ":"
    
    if ASSETS_DIR.exists():
        args.extend(["--add-data", f"{ASSETS_DIR}{sep}assets"])

    # Windows: LibreHardwareMonitor DLL
    if IS_WINDOWS and LIBS_DIR.exists():
        args.extend(["--add-data", f"{LIBS_DIR};libs"])
    
    # macOS: 原生库
    if IS_MACOS and LIBS_DIR.exists():
        args.extend(["--add-data", f"{LIBS_DIR}:libs"])
        # 也添加到macos_native目录
        if MACOS_NATIVE_DIR.exists():
            args.extend(["--add-data", f"{MACOS_NATIVE_DIR}:macos_native"])

    # ======= 新增: 打包 sftool 工具 =======
    if TOOLS_DIR.exists():
        sftool = check_sftool()
        if sftool:
            # 添加 tools 目录到打包资源
            args.extend(["--add-data", f"{TOOLS_DIR}{sep}tools"])
            print(f"[OK] 将打包 sftool: {sftool}")
            
            # macOS: 将 sftool 添加为二进制文件以保留执行权限
            if IS_MACOS:
                args.extend(["--add-binary", f"{sftool}:tools"])
        else:
            print("[WARN] sftool 未找到，固件更新功能将不可用")

    # 隐藏导入
    hidden_imports = [
        "flet",
        "flet_core",
        "psutil",
        "serial",
        "serial.tools.list_ports",
        "requests",
        "PIL",
        "pystray",
    ]
    if IS_WINDOWS:
        # pythonnet 和 wmi 用于硬件监控
        hidden_imports.extend([
            "clr",
            "wmi",
            "pythonnet",
            "clr_loader",
            "clr_loader.ffi",
        ])

    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])

    # Windows: 收集 pythonnet 的所有子模块
    if IS_WINDOWS:
        args.extend(["--collect-submodules", "clr"])
        args.extend(["--collect-submodules", "clr_loader"])
        args.extend(["--collect-all", "pythonnet"])

    excludes = ["tkinter", "test", "unittest"]
    for exc in excludes:
        args.extend(["--exclude-module", exc])

    args.append("main.py")

    # 打印完整命令以便调试
    print("\n[DEBUG] Full PyInstaller command:")
    print(" ".join(args))
    print()
    sys.stdout.flush()

    result = run_cmd(args)
    if result != 0:
        print("[FAIL] PyInstaller 构建失败")
        print(f"[DEBUG] Exit code: {result}")
        # 检查是否有 PyInstaller 日志
        warn_log = BUILD_DIR / "SuperKeyHUB" / "warn-SuperKeyHUB.txt"
        if warn_log.exists():
            print(f"\n[DEBUG] PyInstaller warnings ({warn_log}):")
            with open(warn_log, encoding='utf-8', errors='replace') as f:
                print(f.read())
        return False

    print("[OK] PyInstaller 构建成功")
    return True


# ============================================================================
# 平台特定打包
# ============================================================================
def build_nsis_installer() -> bool:
    """构建 Windows NSIS 安装程序"""
    print_header("[PKG] 构建 Windows NSIS 安装程序")

    nsis_script = PROJECT_ROOT / "installer.nsi"
    if not nsis_script.exists():
        print("[FAIL] 未找到 installer.nsi")
        return False

    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",
    ]

    makensis: str | None = None
    for path in nsis_paths:
        if os.path.exists(path) or shutil.which(path):
            makensis = path
            break

    if not makensis:
        print("[WARN] 未找到 NSIS")
        return False

    result = run_cmd([makensis, str(nsis_script)], cwd=PROJECT_ROOT)
    if result != 0:
        print("[FAIL] NSIS 构建失败")
        return False

    print("[OK] NSIS 安装程序构建成功")
    return True


def build_macos_app() -> bool:
    """构建 macOS .app"""
    print_header("[MACOS] 处理 macOS 应用包")
    
    app_path = DIST_DIR / f"{APP_NAME}.app"
    pyinstaller_app = DIST_DIR / APP_NAME / f"{APP_NAME}.app"
    
    if pyinstaller_app.exists() and not app_path.exists():
        shutil.move(str(pyinstaller_app), str(app_path))
    
    if app_path.exists():
        # 确保 tools/sftool 有执行权限
        sftool_in_app = app_path / "Contents" / "Resources" / "tools" / "sftool"
        if sftool_in_app.exists():
            os.chmod(sftool_in_app, 0o755)
            print(f"[OK] 已设置 sftool 执行权限: {sftool_in_app}")
        
        print(f"[OK] 应用包: {app_path}")
        return True
    
    return False


def build_dmg() -> bool:
    """构建 macOS DMG"""
    print_header("[MACOS] 构建 DMG")
    
    app_path = DIST_DIR / f"{APP_NAME}.app"
    if not app_path.exists():
        print("[FAIL] 未找到 .app")
        return False
    
    dmg_path = DIST_DIR / f"{APP_NAME}-{APP_VERSION}.dmg"
    
    if dmg_path.exists():
        dmg_path.unlink()
    
    # 使用 hdiutil
    result = run_cmd([
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", str(app_path),
        "-ov",
        "-format", "UDZO",
        str(dmg_path),
    ])
    
    if result != 0:
        print("[FAIL] DMG 构建失败")
        return False
    
    print(f"[OK] DMG: {dmg_path}")
    return True


# ============================================================================
# 完整构建流程
# ============================================================================
def build_all(skip_installer: bool = False, skip_deps: bool = False) -> int:
    """完整构建流程
    
    Args:
        skip_installer: 跳过安装程序打包
        skip_deps: 跳过依赖安装（用于 CI 环境，依赖已预先安装）
    """
    print_header(f"[BUILD] SuperKeyHUB v{APP_VERSION} 完整构建")
    print(f"   平台: {SYSTEM}")

    clean_build()

    # 确保依赖已安装（Windows 需要 pythonnet 和 wmi，构建需要 dev 组）
    if not skip_deps:
        print_header("[PKG] 确保依赖已安装")
        if IS_WINDOWS:
            run_cmd(["uv", "sync", "--extra", "windows", "--group", "dev"])
        else:
            run_cmd(["uv", "sync", "--group", "dev"])
    else:
        print("[SKIP] 跳过依赖安装（--skip-deps）")

    # 检查外部工具
    prepare_tools_dir()

    # macOS: 先编译原生库
    if IS_MACOS:
        if not build_macos_native():
            print("[WARN] macOS原生库编译失败，继续构建...")

    if not lint_code():
        print("[WARN] Lint 检查有 error，继续构建...")

    if not build_pyinstaller():
        return 1

    if not skip_installer:
        if IS_WINDOWS:
            build_nsis_installer()
        elif IS_MACOS:
            build_macos_app()
            build_dmg()

    print()
    print("[DONE] 构建完成!")
    print(f"   输出目录: {DIST_DIR}")

    return 0


# ============================================================================
# 帮助信息
# ============================================================================
def show_help() -> None:
    """显示帮助信息"""
    help_text = f"""
{APP_NAME} 构建脚本 v{APP_VERSION}
{'=' * 50}

使用方法: uv run python build.py [选项]

依赖管理:
  --install         安装项目依赖
  --dev             安装开发依赖

代码质量:
  --lint            运行 lint 检查 (仅 error)
  --lint-all        运行完整 lint 检查
  --format          格式化代码
  --type-check      运行 mypy 类型检查
  --check           运行所有检查

运行:
  --run             运行应用
  --run-minimized   最小化启动应用

原生库 (macOS):
  --build-native    编译macOS原生硬件传感器库
  --install-native  安装原生库到系统 (需要sudo)

构建:
  --all             完整构建流程 (推荐)
  --no-installer    构建但跳过安装程序打包
  --skip-deps       跳过依赖安装 (用于 CI 环境)
  --clean           清理构建目录

其他:
  --help, -h        显示此帮助信息

外部工具:
  构建前请将 sftool 放置在 tools/ 目录:
    - Windows: tools/sftool.exe
    - macOS/Linux: tools/sftool

示例:
  uv run python build.py --install        # 首次安装依赖
  uv run python build.py --build-native   # 编译macOS原生库
  uv run python build.py --all            # 完整构建
  uv run python build.py --run            # 运行应用
"""
    print(help_text)


# ============================================================================
# 主函数
# ============================================================================
def main() -> int:
    """主入口"""
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} 构建脚本",
        add_help=False
    )

    parser.add_argument("--install", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--lint", action="store_true")
    parser.add_argument("--lint-all", action="store_true")
    parser.add_argument("--format", action="store_true")
    parser.add_argument("--type-check", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--run-minimized", action="store_true")
    parser.add_argument("--build-native", action="store_true")
    parser.add_argument("--install-native", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-installer", action="store_true")
    parser.add_argument("--skip-deps", action="store_true",
                        help="跳过依赖安装（用于 CI 环境）")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--help", "-h", action="store_true")

    args = parser.parse_args()

    if len(sys.argv) == 1 or args.help:
        show_help()
        return 0

    if args.install:
        return install_deps()

    if args.dev:
        return install_dev_deps()

    if args.clean:
        clean_build()
        return 0

    if args.format:
        format_code()
        return 0

    if args.lint:
        return 0 if lint_code() else 1

    if args.lint_all:
        return 0 if lint_all() else 1

    if args.type_check:
        return 0 if type_check() else 1

    if args.check:
        lint_ok = lint_code()
        type_ok = type_check()
        return 0 if (lint_ok and type_ok) else 1

    if args.run:
        return run_app()

    if args.run_minimized:
        return run_app(minimized=True)

    if args.build_native:
        return 0 if build_macos_native() else 1

    if args.install_native:
        return 0 if install_macos_native_system() else 1

    if args.all:
        return build_all(skip_installer=False, skip_deps=args.skip_deps)

    if args.no_installer:
        return build_all(skip_installer=True, skip_deps=args.skip_deps)

    show_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())