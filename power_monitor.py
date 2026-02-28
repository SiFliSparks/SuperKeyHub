"""
ONLY Windows 电源状态监控

"""

import sys
import threading
import logging
import time

logger = logging.getLogger(__name__)


class PowerMonitor:

    def __init__(self, serial_assistant):
        """
        Args:
            serial_assistant: SerialAssistant 实例，用于发送串口命令
        """
        self._serial = serial_assistant
        self._enabled = False
        self._running = False
        self._thread = None
        self._hwnd = None
        self._is_sleeping = False  # 防止重复触发

    # =========================================================================
    # 公共接口
    # =========================================================================

    def set_enabled(self, enabled: bool):
        """设置是否启用休眠联动"""
        self._enabled = enabled
        logger.info(f"[PowerMonitor] {'启用' if enabled else '禁用'}休眠联动")

    def is_enabled(self) -> bool:
        return self._enabled

    def start(self):
        """开始监听电源事件"""
        if sys.platform != "win32":
            logger.info("[PowerMonitor] 非 Windows 平台，跳过电源监听")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._win32_message_loop,
            name="PowerMonitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("[PowerMonitor] 电源监听已启动")

    def stop(self):
        """停止监听"""
        self._running = False
        if self._hwnd and sys.platform == "win32":
            try:
                import ctypes
                WM_CLOSE = 0x0010
                ctypes.windll.user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        self._hwnd = None
        logger.info("[PowerMonitor] 电源监听已停止")

    # =========================================================================
    # 串口命令发送
    # =========================================================================

    def _send_sleep_command(self):
        """发送休眠命令到设备"""
        if not self._enabled:
            return
        if self._is_sleeping:
            return  # 已经在休眠状态，不重复发送
        self._is_sleeping = True
        try:
            if self._serial and self._serial.is_connected:
                self._serial.send_data("sys_set power_mode sleep\n")
                logger.info("[PowerMonitor] → 设备休眠命令已发送")
            else:
                logger.warning("[PowerMonitor] 串口未连接，无法发送休眠命令")
        except Exception as e:
            logger.error(f"[PowerMonitor] 发送休眠命令失败: {e}")

    def _send_wakeup_command(self):
        """发送唤醒命令到设备"""
        if not self._enabled:
            return
        if not self._is_sleeping:
            return  # 不在休眠状态，不需要唤醒
        self._is_sleeping = False
        try:
            if self._serial and self._serial.is_connected:
                self._serial.send_data("sys_set power_mode normal\n")
                logger.info("[PowerMonitor] → 设备唤醒命令已发送")
            else:
                logger.info("[PowerMonitor] 串口未连接，等待自动重连后发送唤醒命令")
                threading.Thread(
                    target=self._wait_and_send_wakeup,
                    name="WakeupRetry",
                    daemon=True,
                ).start()
        except Exception as e:
            logger.error(f"[PowerMonitor] 发送唤醒命令失败: {e}")

    def _wait_and_send_wakeup(self):
        """等待串口重连后发送唤醒命令"""
        for i in range(15):
            time.sleep(1.0)
            if not self._enabled or not self._running:
                return
            try:
                if self._serial and self._serial.is_connected:
                    self._serial.send_data("sys_set power_mode normal\n")
                    logger.info(f"[PowerMonitor] → 重连后发送唤醒命令 (等待了{i+1}秒)")
                    return
            except Exception:
                continue
        logger.warning("[PowerMonitor] 等待重连超时，唤醒命令未发送")

    # =========================================================================
    # Win32 消息循环 (Modern Standby 兼容)
    # =========================================================================

    def _win32_message_loop(self):
        """创建窗口并通过 RegisterPowerSettingNotification 监听电源状态"""
        try:
            import ctypes
            import ctypes.wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # 声明函数签名（64位兼容）
            user32.DefWindowProcW.argtypes = [
                ctypes.wintypes.HWND, ctypes.c_uint,
                ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
            ]
            user32.DefWindowProcW.restype = ctypes.c_long
            user32.CreateWindowExW.restype = ctypes.wintypes.HWND
            user32.RegisterPowerSettingNotification.argtypes = [
                ctypes.wintypes.HANDLE, ctypes.c_void_p, ctypes.wintypes.DWORD
            ]
            user32.RegisterPowerSettingNotification.restype = ctypes.wintypes.HANDLE

            # 常量
            WM_POWERBROADCAST = 0x0218
            WM_DESTROY = 0x0002
            PBT_APMSUSPEND = 0x0004
            PBT_APMRESUMEAUTOMATIC = 0x0012
            PBT_APMRESUMESUSPEND = 0x0007
            PBT_POWERSETTINGCHANGE = 0x8013
            DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

            # GUID 结构
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            class POWERBROADCAST_SETTING(ctypes.Structure):
                _fields_ = [
                    ("PowerSetting", GUID),
                    ("DataLength", ctypes.wintypes.DWORD),
                    ("Data", ctypes.c_ubyte * 1),
                ]

            def make_guid(s):
                parts = s.split('-')
                g = GUID()
                g.Data1 = int(parts[0], 16)
                g.Data2 = int(parts[1], 16)
                g.Data3 = int(parts[2], 16)
                d4_bytes = bytes.fromhex(parts[3] + parts[4])
                g.Data4 = (ctypes.c_ubyte * 8)(*d4_bytes)
                return g

            def guid_equal(g1, g2):
                return (g1.Data1 == g2.Data1 and g1.Data2 == g2.Data2 and
                        g1.Data3 == g2.Data3 and bytes(g1.Data4) == bytes(g2.Data4))

            # 显示器状态 GUID (Modern Standby 核心)
            GUID_CONSOLE_DISPLAY_STATE = make_guid("6FE69556-704A-47A0-8F24-C28D936FDA47")

            # 引用 self 供回调使用
            monitor = self

            WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.wintypes.HWND, ctypes.c_uint,
                ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
            )

            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_POWERBROADCAST:
                    # 传统 S3 睡眠事件
                    if wparam == PBT_APMSUSPEND:
                        logger.info("[PowerMonitor] ⚡ 检测到系统休眠 (传统)")
                        monitor._send_sleep_command()

                    elif wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
                        logger.info("[PowerMonitor] ⚡ 检测到系统唤醒 (传统)")
                        monitor._send_wakeup_command()

                    # Modern Standby: PowerSettingChange
                    elif wparam == PBT_POWERSETTINGCHANGE and lparam:
                        try:
                            pbs = ctypes.cast(
                                lparam,
                                ctypes.POINTER(POWERBROADCAST_SETTING)
                            ).contents
                            data_ptr = ctypes.addressof(pbs) + POWERBROADCAST_SETTING.Data.offset
                            value = ctypes.c_ulong.from_address(data_ptr).value

                            if guid_equal(pbs.PowerSetting, GUID_CONSOLE_DISPLAY_STATE):
                                if value == 0:
                                    # 显示器关闭 = 进入睡眠
                                    logger.info("[PowerMonitor] ⚡ 检测到系统睡眠 (Modern Standby)")
                                    monitor._send_sleep_command()
                                elif value == 1:
                                    # 显示器打开 = 唤醒
                                    logger.info("[PowerMonitor] ⚡ 检测到系统唤醒 (Modern Standby)")
                                    monitor._send_wakeup_command()
                                # value == 2 (变暗) 忽略

                        except Exception as e:
                            logger.error(f"[PowerMonitor] 解析电源事件异常: {e}")

                    return 1

                elif msg == WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0

                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            # 防止 GC 回收回调
            self._wnd_proc_ref = WNDPROC(wnd_proc)

            class WNDCLASS(ctypes.Structure):
                _fields_ = [
                    ("style", ctypes.c_uint),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.wintypes.HANDLE),
                    ("hIcon", ctypes.wintypes.HANDLE),
                    ("hCursor", ctypes.wintypes.HANDLE),
                    ("hbrBackground", ctypes.wintypes.HANDLE),
                    ("lpszMenuName", ctypes.wintypes.LPCWSTR),
                    ("lpszClassName", ctypes.wintypes.LPCWSTR),
                ]

            hInstance = kernel32.GetModuleHandleW(None)
            class_name = "SuperKeyPowerMonitor"

            wc = WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc_ref
            wc.hInstance = hInstance
            wc.lpszClassName = class_name

            atom = user32.RegisterClassW(ctypes.byref(wc))
            if not atom:
                logger.error(f"[PowerMonitor] RegisterClassW 失败: {kernel32.GetLastError()}")
                return

            # 创建普通隐藏窗口（不用 HWND_MESSAGE，确保收到广播）
            self._hwnd = user32.CreateWindowExW(
                0, class_name, "SuperKey Power", 0,
                0, 0, 0, 0,
                None, None, hInstance, None,
            )

            if not self._hwnd:
                logger.error(f"[PowerMonitor] CreateWindowExW 失败: {kernel32.GetLastError()}")
                user32.UnregisterClassW(class_name, hInstance)
                return

            # 注册 Modern Standby 电源通知
            h_notify = user32.RegisterPowerSettingNotification(
                self._hwnd,
                ctypes.byref(GUID_CONSOLE_DISPLAY_STATE),
                DEVICE_NOTIFY_WINDOW_HANDLE,
            )

            logger.info(f"[PowerMonitor] 窗口已创建 (hwnd={self._hwnd}), "
                        f"电源通知={'已注册' if h_notify else '注册失败'}")

            # 消息循环
            msg = ctypes.wintypes.MSG()
            while self._running:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            # 清理
            if h_notify:
                user32.UnregisterPowerSettingNotification(h_notify)
            if self._hwnd:
                user32.DestroyWindow(self._hwnd)
                self._hwnd = None
            user32.UnregisterClassW(class_name, hInstance)
            logger.info("[PowerMonitor] 消息循环已退出")

        except ImportError:
            logger.warning("[PowerMonitor] 无法导入 ctypes，电源监听不可用")
        except Exception as e:
            logger.error(f"[PowerMonitor] 消息循环异常: {e}", exc_info=True)