"""窗口管理器 - 定位并管理微信小程序窗口"""
import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from loguru import logger

import pygetwindow as gw


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


class WindowManager:
    TARGET_CLIENT_WIDTH = 540
    TARGET_CLIENT_HEIGHT = 960

    def __init__(self):
        self._cached_window: WindowInfo | None = None

    def find_window(self, title_keyword: str = "QQ经典农场") -> WindowInfo | None:
        """通过标题关键词查找窗口"""
        try:
            # 先精确搜索
            windows = gw.getWindowsWithTitle(title_keyword)

            # 没找到则模糊搜索
            if not windows:
                all_windows = gw.getAllWindows()
                for w in all_windows:
                    t = w.title.lower()
                    kw = title_keyword.lower()
                    # 支持部分匹配：QQ农场 能匹配 QQ经典农场
                    if kw in t or all(k in t for k in kw.split()):
                        windows = [w]
                        break

            # 再试一次：只用"农场"关键词
            if not windows:
                for w in gw.getAllWindows():
                    if "农场" in w.title:
                        windows = [w]
                        logger.info(f"通过'农场'关键词找到窗口: {w.title}")
                        break
            if not windows:
                logger.warning(f"未找到包含 '{title_keyword}' 的窗口")
                return None

            w = windows[0]
            info = WindowInfo(
                hwnd=w._hWnd,
                title=w.title,
                left=w.left,
                top=w.top,
                width=w.width,
                height=w.height,
            )
            self._cached_window = info
            logger.debug(f"找到窗口: {info.title} ({info.width}x{info.height})")
            return info
        except Exception as e:
            logger.error(f"查找窗口失败: {e}")
            return None

    def get_window_rect(self) -> tuple[int, int, int, int] | None:
        """获取缓存窗口的区域 (left, top, width, height)"""
        if not self._cached_window:
            return None
        w = self._cached_window
        return (w.left, w.top, w.width, w.height)

    def activate_window(self) -> bool:
        """激活并置顶窗口"""
        if not self._cached_window:
            return False
        try:
            hwnd = self._cached_window.hwnd
            # 使用win32 API置顶窗口
            SW_RESTORE = 9
            ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            logger.debug("窗口已激活")
            return True
        except Exception as e:
            logger.error(f"激活窗口失败: {e}")
            return False

    @staticmethod
    def _calculate_position(work_area: ctypes.wintypes.RECT,
                            window_width: int, window_height: int,
                            position: str = "left_center") -> tuple[int, int]:
        """根据工作区计算窗口左上角坐标"""
        wa_left, wa_top = work_area.left, work_area.top
        wa_right, wa_bottom = work_area.right, work_area.bottom
        wa_width = wa_right - wa_left
        wa_height = wa_bottom - wa_top

        if position == "center":
            x = wa_left + (wa_width - window_width) // 2
            y = wa_top + (wa_height - window_height) // 2
        elif position == "right_center":
            x = wa_right - window_width
            y = wa_top + (wa_height - window_height) // 2
        elif position == "top_left":
            x = wa_left
            y = wa_top
        elif position == "top_right":
            x = wa_right - window_width
            y = wa_top
        else:
            # 默认：左侧中央
            x = wa_left
            y = wa_top + (wa_height - window_height) // 2

        # 边界保护，避免超出工作区
        x = max(wa_left, min(x, wa_right - window_width))
        y = max(wa_top, min(y, wa_bottom - window_height))
        return x, y

    def resize_window(self, position: str = "left_center") -> bool:
        """按客户区大小调整窗口并放置到指定位置（目标 540x960）"""
        if not self._cached_window:
            return False
        try:
            hwnd = self._cached_window.hwnd
            client_width = self.TARGET_CLIENT_WIDTH
            client_height = self.TARGET_CLIENT_HEIGHT

            user32 = ctypes.windll.user32
            # 获取当前窗口 style / ex_style
            style = user32.GetWindowLongW(hwnd, -16)    # GWL_STYLE
            ex_style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE

            # 计算包含边框与标题栏后的窗口尺寸
            rect = ctypes.wintypes.RECT(0, 0, int(client_width), int(client_height))
            adjusted = False
            try:
                get_dpi_for_window = user32.GetDpiForWindow
                adjust_for_dpi = user32.AdjustWindowRectExForDpi
                dpi = int(get_dpi_for_window(hwnd))
                adjusted = bool(adjust_for_dpi(ctypes.byref(rect), style, False, ex_style, dpi))
                if not adjusted:
                    logger.warning("AdjustWindowRectExForDpi 调用失败，回退到 AdjustWindowRectEx")
            except Exception:
                adjusted = False

            if not adjusted:
                ok = user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
                if not ok:
                    logger.error("调整窗口大小失败: AdjustWindowRectEx 调用失败")
                    return False

            window_width = rect.right - rect.left
            window_height = rect.bottom - rect.top

            # 获取主屏工作区域（排除任务栏）
            work_area = ctypes.wintypes.RECT()
            user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0)

            pos_x, pos_y = self._calculate_position(
                work_area, window_width, window_height, position
            )
            user32.MoveWindow(hwnd, pos_x, pos_y, window_width, window_height, True)
            self._cached_window.left = pos_x
            self._cached_window.top = pos_y
            self._cached_window.width = window_width
            self._cached_window.height = window_height

            logger.info(
                f"窗口客户区设置为 {client_width}x{client_height}，"
                f"窗口外框 {window_width}x{window_height}，位置({pos_x},{pos_y}) [{position}]"
            )
            return True
        except Exception as e:
            logger.error(f"调整窗口大小失败: {e}")
            return False

    def is_window_visible(self) -> bool:
        """检查窗口是否可见"""
        if not self._cached_window:
            return False
        try:
            return bool(ctypes.windll.user32.IsWindowVisible(self._cached_window.hwnd))
        except Exception:
            return False

    def refresh_window_info(self, title_keyword: str = "QQ农场") -> WindowInfo | None:
        """刷新窗口位置信息"""
        return self.find_window(title_keyword)
