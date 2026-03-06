# SuperKeyHUB

配合SuperKey设备完成各种功能的实现

## 更新日志
[点击查看最新日志](https://sparks.sifli.com/projects/superkey/custom/newlab.html)

## 功能特性
- 硬件性能监控 — CPU/GPU/内存/磁盘/网络实时数据采集与下发
- - Windows: PDH + LibreHardwareMonitor + psutil 混合架构
- - macOS: IOKit + psutil
- 天气信息 — 和风天气 API，支持当前天气与三日预报
- 自定义按键 — 可视化配置 HID 键盘按键映射
- LED 灯效控制 — 颜色、亮度、呼吸/流动/彩虹等效果
- 跟随系统休眠 — Windows 休眠/唤醒自动联动设备息屏/亮屏
- 屏幕旋转 — 远程控制设备屏幕 0°/90°/180°/270° 旋转
- 固件更新 (OTA) — 通过串口烧录固件
- 应用自更新 — 检查新版本、下载安装一键完成
- 系统托盘 — 最小化到托盘后台运行

## 快速开始

### 运行

```bash
# Windows
uv run --extra windows python main.py

# macOS / Linux
uv run python main.py
```

### 构建安装包

```bash
# 安装开发依赖
uv sync --group dev

# 运行构建脚本（生成 PyInstaller 打包 + NSIS 安装程序）
uv run python build.py
```

构建产物位于 `dist/` 目录。

## 项目结构

```
SuperKeyHub/
├── main.py                 # 主程序入口，Flet UI
├── hw_monitor.py           # 硬件性能监控（PDH/LHM/psutil/IOKit）
├── serial_assistant.py     # 串口通信（UART + CDC 双通道）
├── finsh_data_sender.py    # 性能数据定时下发
├── weather_api.py          # 和风天气 API 客户端
├── config_manager.py       # 配置持久化管理
├── custom_key_manager.py   # 自定义按键配置
├── led_controller.py       # LED 灯效控制
├── power_monitor.py        # Windows 电源状态监控
├── firmware_updater.py     # 固件 OTA 更新 + 版本检测
├── app_updater.py          # 应用自更新
├── system_tray.py          # 系统托盘 + 开机自启
├── build.py                # PyInstaller 构建脚本
├── installer.nsi           # NSIS 安装程序脚本
├── pyproject.toml          # 项目配置与依赖
├── assets/                 # 图标资源
├── libs/                   # LHM DLL（Windows）
└── tools/                  # sftool 烧录工具
```

## 串口通信协议

上位机通过 `sys_set` 命令向设备下发数据：

```
sys_set time "14:30:00"          # 时间同步
sys_set cpu 45.2                 # CPU 使用率
sys_set cpu_temp 65.0            # CPU 温度
sys_set cpu_freq 4938            # CPU 频率 (MHz)
sys_set gpu 30.0                 # GPU 使用率
sys_set gpu_temp 55.0            # GPU 温度
sys_set gpu_mem_used 2.3         # 显存已用 (GB)
sys_set gpu_mem_total 12.0       # 显存总计 (GB)
sys_set mem 62.5                 # 内存占用率
sys_set mem_used 20.0            # 内存已用 (GB)
sys_set mem_total 32.0           # 内存总计 (GB)
sys_set power_mode sleep         # 设备休眠
sys_set power_mode normal        # 设备唤醒
sys_set lcd_rotation 90          # 屏幕旋转
```

通过 `sys_get` 查询设备状态：

```
sys_get version                  # 固件版本
sys_get power_mode               # 电源状态
```

## 开源协议
[Apache-2.0](LICENSE)
