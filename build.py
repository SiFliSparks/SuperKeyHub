#!/usr/bin/env python3
"""
SuperKeyHUB 跨平台构建脚本
统一的项目管理工具，支持依赖安装、代码检查、构建打包

使用方法:
    uv run python build.py --help
    uv run python build.py --install      # 安装依赖
    uv run python build.py --dev          # 安装开发依赖
    uv run python build.py --run          # 运行应用
    uv run python build.py --lint         # 代码检查
    uv run python build.py --format       # 格式化代码
    uv run python build.py --type-check   # 类型检查
    uv run python build.py --all          # 完整构建
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


# ============================================================================
# 工具函数
# ============================================================================
def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = False
) -> int:
    """运行命令并返回退出码"""
    print(f">>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
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
# 依赖管理
# ============================================================================
def install_deps() -> int:
    """安装项目依赖"""
    print_header("[PKG] 安装项目依赖")
    return run_cmd(["uv", "sync"])


def install_dev_deps() -> int:
    """安装开发依赖"""
    print_header("[PKG] 安装开发依赖")
    return run_cmd(["uv", "sync", "--all-extras"])


# ============================================================================
# 代码质量
# ============================================================================
def lint_code(fix: bool = False) -> bool:
    """运行 ruff lint 检查"""
    print_header("[CHECK] 运行 Ruff lint 检查")

    if fix:
        run_cmd(["uv", "run", "ruff", "check", "--fix", "."])

    # 只检查 error 级别 (E, F)
    result = run_cmd(["uv", "run", "ruff", "check", ".", "--select=E,F"])
    if result != 0:
        print("[FAIL] Lint 检查失败 (存在 error)")
        return False
    print("[OK] Lint 检查通过")
    return True


def lint_all() -> bool:
    """运行完整 lint 检查（包括 warning）"""
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
    print_header("[BUILD] 运行应用")
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

    # 清理 PyInstaller spec 文件
    for f in PROJECT_ROOT.glob("*.spec"):
        f.unlink()
        print(f"  已删除: {f}")

    # 递归清理 __pycache__
    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)

    # 清理 .pyc 文件
    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        pyc.unlink()

    print("[OK] 清理完成")


# ============================================================================
# PyInstaller 构建
# ============================================================================
def build_pyinstaller() -> bool:
    """使用 PyInstaller 构建可执行文件"""
    print_header(f"[BUILD] 构建 {APP_NAME}")

    # 基础参数
    args: list[str] = [
        "uv", "run", "pyinstaller",
        "--name", APP_NAME,
        "--windowed",  # GUI 应用
        "--onedir",    # 目录模式，便于调试
        "--clean",
        "--noconfirm",
    ]

    # 添加图标
    if IS_WINDOWS:
        icon_path = ASSETS_DIR / "app.ico"
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])
    elif IS_MACOS:
        icon_path = ASSETS_DIR / "app.icns"
        if icon_path.exists():
            args.extend(["--icon", str(icon_path)])

    # 添加资源文件
    if ASSETS_DIR.exists():
        sep = ";" if IS_WINDOWS else ":"
        args.extend(["--add-data", f"{ASSETS_DIR}{sep}assets"])

    # Windows 特定：添加 LibreHardwareMonitor DLL
    if IS_WINDOWS:
        libs_dir = PROJECT_ROOT / "libs"
        if libs_dir.exists():
            args.extend(["--add-data", f"{libs_dir};libs"])

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
        hidden_imports.extend(["clr", "wmi", "pythonnet"])

    for imp in hidden_imports:
        args.extend(["--hidden-import", imp])

    # 排除不需要的模块
    excludes = ["tkinter", "test", "unittest"]
    for exc in excludes:
        args.extend(["--exclude-module", exc])

    # 主入口
    args.append("main.py")

    result = run_cmd(args)
    if result != 0:
        print("[FAIL] PyInstaller 构建失败")
        return False

    print("[OK] PyInstaller 构建成功")
    return True


# ============================================================================
# Windows NSIS 打包
# ============================================================================
def build_nsis_installer() -> bool:
    """构建 Windows NSIS 安装程序（使用项目中的 installer.nsi）"""
    print_header("[PKG] 构建 Windows NSIS 安装程序")

    # 使用项目根目录下的 installer.nsi
    nsis_script = PROJECT_ROOT / "installer.nsi"
    if not nsis_script.exists():
        print("[FAIL] 未找到 installer.nsi 脚本")
        print(f"   请确保 {nsis_script} 文件存在")
        return False

    # 检查 NSIS 是否安装
    nsis_paths = [
        r"C:\Program Files (x86)\NSIS\makensis.exe",
        r"C:\Program Files\NSIS\makensis.exe",
        "makensis",  # 在 PATH 中
    ]

    makensis: str | None = None
    for path in nsis_paths:
        if os.path.exists(path) or shutil.which(path):
            makensis = path
            break

    if not makensis:
        print("[WARN] 未找到 NSIS，跳过安装程序构建")
        print("   请从 https://nsis.sourceforge.io/ 下载安装 NSIS")
        return False

    # 运行 NSIS（从项目根目录执行，确保相对路径正确）
    result = run_cmd([makensis, str(nsis_script)], cwd=PROJECT_ROOT)
    if result != 0:
        print("[FAIL] NSIS 构建失败")
        return False

    print("[OK] Windows 安装程序构建成功")
    return True


# ============================================================================
# macOS DMG 打包
# ============================================================================
def build_macos_app() -> bool:
    """构建 macOS .app bundle"""
    print_header("[MACOS] 构建 macOS 应用")

    app_path = DIST_DIR / f"{APP_NAME}.app"

    # PyInstaller 应该已经创建了 .app
    if not app_path.exists():
        # 手动创建 .app 结构
        contents = app_path / "Contents"
        macos = contents / "MacOS"
        resources = contents / "Resources"

        ensure_dir(macos)
        ensure_dir(resources)

        # 复制可执行文件
        exe_dir = DIST_DIR / APP_NAME
        if exe_dir.exists():
            for item in exe_dir.iterdir():
                dest = macos / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

        # 创建 Info.plist
        info_plist = contents / "Info.plist"
        info_plist.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>com.superkey.hub</string>
    <key>CFBundleVersion</key>
    <string>{APP_VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>{APP_VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
''')

        # 复制图标
        icon_src = ASSETS_DIR / "app.icns"
        if icon_src.exists():
            shutil.copy2(icon_src, resources / "app.icns")

    print("[OK] macOS 应用构建成功")
    return True


def build_dmg() -> bool:
    """构建 macOS DMG 镜像"""
    print_header("💿 构建 macOS DMG")

    app_path = DIST_DIR / f"{APP_NAME}.app"
    dmg_path = DIST_DIR / f"{APP_NAME}-{APP_VERSION}.dmg"

    if not app_path.exists():
        print("[FAIL] 未找到 .app 文件")
        return False

    result: int = 0

    # 检查 create-dmg 或使用 hdiutil
    if shutil.which("create-dmg"):
        # 使用 create-dmg (brew install create-dmg)
        result = run_cmd([
            "create-dmg",
            "--volname", APP_NAME,
            "--volicon", str(ASSETS_DIR / "app.icns"),
            "--window-pos", "200", "120",
            "--window-size", "600", "400",
            "--icon-size", "100",
            "--icon", f"{APP_NAME}.app", "175", "120",
            "--hide-extension", f"{APP_NAME}.app",
            "--app-drop-link", "425", "120",
            str(dmg_path),
            str(app_path),
        ])
    else:
        # 使用系统 hdiutil
        temp_dmg = DIST_DIR / "temp.dmg"

        # 创建临时 DMG
        run_cmd([
            "hdiutil", "create",
            "-srcfolder", str(app_path),
            "-volname", APP_NAME,
            "-fs", "HFS+",
            "-fsargs", "-c c=64,a=16,e=16",
            "-format", "UDRW",
            str(temp_dmg),
        ])

        # 转换为压缩 DMG
        result = run_cmd([
            "hdiutil", "convert",
            str(temp_dmg),
            "-format", "UDZO",
            "-o", str(dmg_path),
        ])

        # 删除临时文件
        if temp_dmg.exists():
            temp_dmg.unlink()

    if result != 0:
        print("[FAIL] DMG 构建失败")
        return False

    print(f"[OK] DMG 构建成功: {dmg_path}")
    return True


# ============================================================================
# Linux 打包 (AppImage)
# ============================================================================
def build_linux_appimage() -> bool:
    """构建 Linux AppImage"""
    print_header("[LINUX] 构建 Linux AppImage")

    # 检查 appimagetool
    if not shutil.which("appimagetool"):
        print("[WARN] 未找到 appimagetool，跳过 AppImage 构建")
        print("   请从 https://appimage.github.io/ 下载")
        return False

    appdir = BUILD_DIR / f"{APP_NAME}.AppDir"
    ensure_dir(appdir)

    # 创建 AppDir 结构
    usr_bin = appdir / "usr" / "bin"
    usr_share = appdir / "usr" / "share"
    ensure_dir(usr_bin)
    ensure_dir(usr_share / "applications")
    ensure_dir(usr_share / "icons")

    # 复制可执行文件
    exe_dir = DIST_DIR / APP_NAME
    if exe_dir.exists():
        shutil.copytree(exe_dir, usr_bin / APP_NAME)

    # 创建 .desktop 文件
    desktop_file = usr_share / "applications" / f"{APP_NAME.lower()}.desktop"
    desktop_file.write_text(f'''[Desktop Entry]
Type=Application
Name={APP_NAME}
Exec={APP_NAME}
Icon={APP_NAME.lower()}
Categories=Utility;System;
Comment={APP_DESCRIPTION}
''')

    # 复制到 AppDir 根目录
    shutil.copy2(desktop_file, appdir / f"{APP_NAME.lower()}.desktop")

    # 复制图标
    icon_src = ASSETS_DIR / "app.png"
    if icon_src.exists():
        shutil.copy2(icon_src, appdir / f"{APP_NAME.lower()}.png")
        shutil.copy2(icon_src, usr_share / "icons" / f"{APP_NAME.lower()}.png")

    # 创建 AppRun
    apprun = appdir / "AppRun"
    apprun.write_text(f'''#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${{SELF%/*}}
exec "$HERE/usr/bin/{APP_NAME}/{APP_NAME}" "$@"
''')
    apprun.chmod(0o755)

    # 构建 AppImage
    appimage_path = DIST_DIR / f"{APP_NAME}-{APP_VERSION}-x86_64.AppImage"
    result = run_cmd([
        "appimagetool",
        str(appdir),
        str(appimage_path),
    ])

    if result != 0:
        print("[FAIL] AppImage 构建失败")
        return False

    print(f"[OK] AppImage 构建成功: {appimage_path}")
    return True


# ============================================================================
# 完整构建流程
# ============================================================================
def build_all(skip_installer: bool = False) -> int:
    """完整构建流程"""
    print_header(f"[BUILD] SuperKeyHUB v{APP_VERSION} 完整构建")
    print(f"   平台: {SYSTEM}")

    # 清理
    clean_build()

    # Lint 检查 (只检查 error)
    if not lint_code():
        print("[WARN] Lint 检查有 error，继续构建...")

    # PyInstaller 构建
    if not build_pyinstaller():
        return 1

    # 平台特定打包
    if not skip_installer:
        if IS_WINDOWS:
            build_nsis_installer()
        elif IS_MACOS:
            build_macos_app()
            build_dmg()
        elif IS_LINUX:
            build_linux_appimage()

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
  --install         安装项目依赖 (uv sync)
  --dev             安装开发依赖 (uv sync --all-extras)

代码质量:
  --lint            运行 lint 检查 (仅 error)
  --lint-all        运行完整 lint 检查
  --format          格式化代码
  --type-check      运行 mypy 类型检查
  --check           运行所有检查 (lint + type-check)

运行:
  --run             运行应用
  --run-minimized   最小化启动应用

构建:
  --all             完整构建流程 (推荐)
  --no-installer    构建但跳过安装程序打包
  --clean           清理构建目录

其他:
  --help, -h        显示此帮助信息

示例:
  uv run python build.py --install      # 首次安装依赖
  uv run python build.py --dev          # 安装开发依赖
  uv run python build.py --format       # 格式化代码
  uv run python build.py --all          # 完整构建
  uv run python build.py --run          # 运行应用
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

    # 依赖管理
    parser.add_argument("--install", action="store_true",
                        help="安装项目依赖")
    parser.add_argument("--dev", action="store_true",
                        help="安装开发依赖")

    # 代码质量
    parser.add_argument("--lint", action="store_true",
                        help="运行 lint 检查 (仅 error)")
    parser.add_argument("--lint-all", action="store_true",
                        help="运行完整 lint 检查")
    parser.add_argument("--format", action="store_true",
                        help="格式化代码")
    parser.add_argument("--type-check", action="store_true",
                        help="运行 mypy 类型检查")
    parser.add_argument("--check", action="store_true",
                        help="运行所有检查")

    # 运行
    parser.add_argument("--run", action="store_true",
                        help="运行应用")
    parser.add_argument("--run-minimized", action="store_true",
                        help="最小化启动应用")

    # 构建
    parser.add_argument("--all", action="store_true",
                        help="完整构建流程")
    parser.add_argument("--no-installer", action="store_true",
                        help="跳过安装程序构建")
    parser.add_argument("--clean", action="store_true",
                        help="清理构建目录")

    # 帮助
    parser.add_argument("--help", "-h", action="store_true",
                        help="显示帮助信息")

    args = parser.parse_args()

    # 无参数或请求帮助时显示帮助
    if len(sys.argv) == 1 or args.help:
        show_help()
        return 0

    # 依赖管理
    if args.install:
        return install_deps()

    if args.dev:
        return install_dev_deps()

    # 清理
    if args.clean:
        clean_build()
        return 0

    # 格式化
    if args.format:
        format_code()
        return 0

    # Lint
    if args.lint:
        return 0 if lint_code() else 1

    if args.lint_all:
        return 0 if lint_all() else 1

    # 类型检查
    if args.type_check:
        return 0 if type_check() else 1

    # 所有检查
    if args.check:
        lint_ok = lint_code()
        type_ok = type_check()
        return 0 if (lint_ok and type_ok) else 1

    # 运行
    if args.run:
        return run_app()

    if args.run_minimized:
        return run_app(minimized=True)

    # 完整构建
    if args.all:
        return build_all(skip_installer=False)

    # 仅构建 exe
    if args.no_installer:
        return build_all(skip_installer=True)

    # 默认显示帮助
    show_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
