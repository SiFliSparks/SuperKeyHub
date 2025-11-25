# SuperKeyHUB

一个系统监控和api数据收集工具，支持硬件监控、天气股票数据、串口调试。

## 功能特性

- 硬件监控: 实时监控CPU、GPU、内存、磁盘、网络状态
- 天气信息: 支持和风天气API，提供实时天气和预报数据
- 股票行情: 集成第三方API，显示主要股指信息
- 串口调试: 完整的串口通信工具，支持ASCII/HEX格式
- 数据下发: 自定义Finsh协议，向外部设备发送监控数据

## 快速开始
- 克隆仓库
```
git clone https://github.com/OpenSiFli/SuperKeyHub
```
### 环境要求
- Windows 10/11 (推荐)
- Python 3.7+
- .NET Framework 4.7.2+

### 环境安装/构建与快速使用
```bash
cd SuperKeyHub
```
- 仅安装环境
```bash
python setup_dependencies.py
python main.py
```
- 开发者模式（包含构建工具）
```bash
python setup_dependencies.py --dev
python main.py
```
- 仅安装构建工具
```bash
python setup_dependencies.py --build-only
```
- 要构建，请在运行以上命令后，使用
```bash
python build.py --all
```
#### 快速使用方法
- 1.将SuperKey通过USB连接到电脑，确认SuperKey的串口号
- 2.在Hub上的串口配置页面点击串口号旁边的刷新按钮，刷新出SuperKey的串口号
- 3.正确配置波特率1000000，点击连接，并点击数据下发按钮
- 稍等片刻，信息将同步至SuperKey屏幕
## 第三方组件
- LibreHardwareMonitor - Mozilla Public License 2.0
- Flet - Apache-2.0
- psutil - BSD-3-Clause

## 注意事项
- 本项目1.0版本适配SuperKey固件1.0版本。
- 由于SuperKey固件当前版本目标仅为简要演示，实现基础功能，即将推出的固件1.1版本及后续版本将在功能、数据传输及配置实现方式有较大改动，故本上位机后续推出的更新将不予兼容固件1.0版本。
## 致谢
思澈科技（南京）提供全程技术支持
