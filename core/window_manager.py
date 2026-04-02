"""窗口管理器 - 定位并管理微信小程序窗口"""
import ctypes
import ctypes.wintypes
import json
from pathlib import Path
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


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


class WindowManager:
    TARGET_CLIENT_WIDTH = 540
    TARGET_CLIENT_HEIGHT = 960
    _NONCLIENT_JSON_PATH = Path(__file__).resolve().parent.parent / "models" / "window_nonclient_metrics.json"
    _MONITOR_DEFAULTTONEAREST = 2
    _SWP_NOZORDER = 0x0004
    _SWP_NOOWNERZORDER = 0x0200
    _GWL_STYLE = -16
    _GWL_EXSTYLE = -20

    def __init__(self):
        self._enable_dpi_awareness()
        self._cached_window: WindowInfo | None = None
        self._nonclient_config = self._load_nonclient_config()

    @staticmethod
    def _enable_dpi_awareness() -> None:
        """尽量开启 DPI 感知，减少尺寸虚拟化误差。"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    def _load_nonclient_config(self) -> dict:
        """加载窗口边框/标题高度配置。"""
        try:
            with open(self._NONCLIENT_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning(f"加载 nonclient 配置失败: {e}")
        return {}

    @staticmethod
    def _get_window_scale_percent(hwnd: int) -> int:
        """读取窗口 DPI 对应的缩放百分比。"""
        try:
            dpi = int(ctypes.windll.user32.GetDpiForWindow(hwnd))
        except Exception:
            dpi = 96
        scale = int(round((dpi / 96.0) * 100))
        return max(50, min(scale, 500))

    @staticmethod
    def _get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
        rect = ctypes.wintypes.RECT()
        ok = ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if not ok:
            return None
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)

    @staticmethod
    def _get_window_outer_size(hwnd: int) -> tuple[int, int] | None:
        rect = WindowManager._get_window_rect(hwnd)
        if not rect:
            return None
        return int(rect[2] - rect[0]), int(rect[3] - rect[1])

    @staticmethod
    def _get_client_size(hwnd: int) -> tuple[int, int] | None:
        rect = ctypes.wintypes.RECT()
        ok = ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
        if not ok:
            return None
        return int(rect.right - rect.left), int(rect.bottom - rect.top)

    @staticmethod
    def _calc_outer_size_by_adjust_rect(hwnd: int, client_width: int, client_height: int) -> tuple[int, int, int] | None:
        """参考 NIKKE change_resolution_compat：按窗口 style/exstyle + DPI 计算外框尺寸。"""
        try:
            user32 = ctypes.windll.user32
            dpi = 96
            try:
                dpi = int(user32.GetDpiForWindow(hwnd))
            except Exception:
                dpi = 96

            rect = ctypes.wintypes.RECT(0, 0, int(client_width), int(client_height))
            style = int(user32.GetWindowLongW(hwnd, WindowManager._GWL_STYLE))
            ex_style = int(user32.GetWindowLongW(hwnd, WindowManager._GWL_EXSTYLE))

            ok = False
            try:
                ok = bool(user32.AdjustWindowRectExForDpi(ctypes.byref(rect), style, False, ex_style, int(dpi)))
            except Exception:
                ok = bool(user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style))
            if not ok:
                return None

            outer_w = int(rect.right - rect.left)
            outer_h = int(rect.bottom - rect.top)
            return outer_w, outer_h, int(dpi)
        except Exception:
            return None


    def _get_work_area_for_window(self, hwnd: int) -> ctypes.wintypes.RECT | None:
        user32 = ctypes.windll.user32
        monitor = 0
        try:
            monitor = user32.MonitorFromWindow(ctypes.wintypes.HWND(hwnd), self._MONITOR_DEFAULTTONEAREST)
        except Exception:
            monitor = 0
        if monitor:
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            ok = bool(user32.GetMonitorInfoW(monitor, ctypes.byref(monitor_info)))
            if ok:
                return ctypes.wintypes.RECT(
                    monitor_info.rcWork.left,
                    monitor_info.rcWork.top,
                    monitor_info.rcWork.right,
                    monitor_info.rcWork.bottom,
                )

        work_area = ctypes.wintypes.RECT()
        ok = bool(user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work_area), 0))
        if not ok:
            return None
        return work_area

    def _set_window_outer_rect(self, hwnd: int, x: int, y: int, width: int, height: int) -> tuple[bool, str]:
        user32 = ctypes.windll.user32
        ok = bool(
            user32.SetWindowPos(
                hwnd,
                0,
                int(x),
                int(y),
                int(width),
                int(height),
                self._SWP_NOZORDER | self._SWP_NOOWNERZORDER,
            )
        )
        if ok:
            return True, "SetWindowPos"
        ok = bool(user32.MoveWindow(hwnd, int(x), int(y), int(width), int(height), True))
        if ok:
            return True, "MoveWindow"
        return False, "SetWindowPos/MoveWindow failed"

    def _set_window_outer_size_with_retry(
        self,
        hwnd: int,
        x: int,
        y: int,
        target_outer_width: int,
        target_outer_height: int,
        max_rounds: int = 6,
        verbose_log: bool = False,
    ) -> tuple[bool, str]:
        """参考 debug 脚本：按外框误差迭代修正。"""
        current_w = int(target_outer_width)
        current_h = int(target_outer_height)
        apply_method = "unknown"

        for round_idx in range(1, max_rounds + 1):
            ok, apply_method = self._set_window_outer_rect(hwnd, x, y, current_w, current_h)
            if not ok:
                return False, f"resize failed at round {round_idx}: {apply_method}"

            outer_size = self._get_window_outer_size(hwnd)
            if not outer_size:
                return False, f"resize failed at round {round_idx}: cannot read window rect"

            err_w = int(target_outer_width - outer_size[0])
            err_h = int(target_outer_height - outer_size[1])
            if verbose_log:
                logger.info(
                    f"[wechat-resize][outer] round={round_idx} "
                    f"request={current_w}x{current_h} actual={outer_size[0]}x{outer_size[1]} "
                    f"err=({err_w},{err_h}) apply={apply_method}"
                )
            if err_w == 0 and err_h == 0:
                return True, (
                    f"resize success in {round_idx} rounds; "
                    f"actual_outer={outer_size[0]}x{outer_size[1]}; apply={apply_method}"
                )

            current_w = max(120, int(current_w + err_w))
            current_h = max(120, int(current_h + err_h))

        final_outer = self._get_window_outer_size(hwnd)
        if not final_outer:
            return False, "resize reached max rounds; cannot read final outer size"
        return False, (
            f"resize reached max rounds; final_outer={final_outer[0]}x{final_outer[1]}, "
            f"target_outer={target_outer_width}x{target_outer_height}; apply={apply_method}"
        )

    def _get_nonclient_metrics(self, platform: str, scale_percent: int) -> tuple[int, int, int]:
        """按平台+缩放取边框/标题高度；缩放值使用最近匹配。"""
        cfg = self._nonclient_config or {}
        platforms = cfg.get("platforms", {}) if isinstance(cfg, dict) else {}
        platform_key = (platform or "").strip().lower()
        if platform_key not in platforms:
            platform_key = str(cfg.get("default_platform", "qq")).lower()
        platform_cfg = platforms.get(platform_key, {})
        scales = platform_cfg.get("scales", {}) if isinstance(platform_cfg, dict) else {}

        valid_pairs: list[tuple[int, dict]] = []
        for k, v in scales.items():
            try:
                valid_pairs.append((int(k), v))
            except Exception:
                continue
        if not valid_pairs:
            # 兜底：QQ 100%
            return 1, 39, 100

        matched_scale, matched_value = min(valid_pairs, key=lambda item: abs(item[0] - int(scale_percent)))
        border = int(matched_value.get("border_width", 1))
        title = int(matched_value.get("title_height", 39))
        return border, title, matched_scale

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
        elif position == "left_bottom":
            x = wa_left
            y = wa_bottom - window_height
        elif position == "right_bottom":
            x = wa_right - window_width
            y = wa_bottom - window_height
        else:
            # 默认：左侧中央
            x = wa_left
            y = wa_top + (wa_height - window_height) // 2

        # 边界保护，避免超出工作区
        x = max(wa_left, min(x, wa_right - window_width))
        y = max(wa_top, min(y, wa_bottom - window_height))
        return x, y

    def resize_window(self, position: str = "left_center", platform: str = "qq") -> bool:
        """设置窗口分辨率与位置。"""
        if not self._cached_window:
            return False
        try:
            hwnd = self._cached_window.hwnd
            base_width = self.TARGET_CLIENT_WIDTH
            base_height = self.TARGET_CLIENT_HEIGHT

            scale_percent = self._get_window_scale_percent(hwnd)
            border_width, title_height, matched_scale = self._get_nonclient_metrics(platform, scale_percent)
            platform_key = (platform or "").strip().lower()
            is_wechat = platform_key in ("wechat", "wx", "weixin")
            target_client_w = int(base_width)
            target_client_h = int(base_height)
            before_outer = self._get_window_outer_size(hwnd)
            before_client = self._get_client_size(hwnd)

            if not before_outer or not before_client:
                logger.error("调整窗口大小失败: 无法读取当前窗口 outer/client 尺寸")
                return False

            # tools/resize_window.py: 动态 nonclient
            nonclient_w = max(0, int(before_outer[0] - before_client[0]))
            nonclient_h = max(0, int(before_outer[1] - before_client[1]))

            # 目标物理尺寸（target_physical_w/h）
            # 1) 微信: 540 x (960 + border + title)
            # 2) QQ  : (540 + border*2) x (960 + border*2 + title)
            if is_wechat:
                target_physical_w = int(base_width)
                target_physical_h = int(base_height + border_width + title_height)

                # tools: 微信最终尺寸 = target_physical + 当前 nonclient
                target_outer_w = int(target_physical_w + nonclient_w)
                target_outer_h = int(target_physical_h + nonclient_h)

                width_add = 0
                height_add = int(border_width + title_height)
                formula_desc = "wechat(tools): final=(target_physical + nonclient)"
            else:
                target_physical_w = int(base_width + border_width * 2)
                target_physical_h = int(base_height + border_width * 2 + title_height)

                # tools: QQ 最终尺寸 = target_physical（不额外加 nonclient）
                target_outer_w = int(target_physical_w)
                target_outer_h = int(target_physical_h)

                width_add = int(border_width * 2)
                height_add = int(border_width * 2 + title_height)
                formula_desc = "qq(tools): final=target_physical"

            work_area = self._get_work_area_for_window(hwnd)
            if not work_area:
                logger.error("调整窗口大小失败: 无法获取工作区")
                return False

            pos_x, pos_y = self._calculate_position(work_area, target_outer_w, target_outer_h, position)

            before_outer_text = f"{before_outer[0]}x{before_outer[1]}" if before_outer else "unknown"
            before_client_text = f"{before_client[0]}x{before_client[1]}" if before_client else "unknown"
            logger.info(
                f"[resize][begin] formula={formula_desc} before_outer={before_outer_text} "
                f"before_client={before_client_text} target_outer={target_outer_w}x{target_outer_h} "
                f"target_client={target_client_w}x{target_client_h} "
                f"nonclient={nonclient_w}x{nonclient_h} position={position} target_xy=({pos_x},{pos_y})"
            )

            ok, apply_method = self._set_window_outer_rect(
                hwnd=hwnd,
                x=pos_x,
                y=pos_y,
                width=target_outer_w,
                height=target_outer_h,
            )
            if not ok:
                logger.error(f"调整窗口大小失败: {apply_method}")
                return False

            resize_msg = (
                f"resize applied once; actual_outer={target_outer_w}x{target_outer_h}; apply={apply_method}"
            )

            final_rect = self._get_window_rect(hwnd)
            final_client = self._get_client_size(hwnd)
            if final_rect:
                self._cached_window.left = int(final_rect[0])
                self._cached_window.top = int(final_rect[1])
                self._cached_window.width = int(final_rect[2] - final_rect[0])
                self._cached_window.height = int(final_rect[3] - final_rect[1])
            else:
                self._cached_window.left = pos_x
                self._cached_window.top = pos_y
                self._cached_window.width = target_outer_w
                self._cached_window.height = target_outer_h

            actual_client_text = f"{final_client[0]}x{final_client[1]}" if final_client else "unknown"
            err_w = int(target_client_w - final_client[0]) if final_client else 0
            err_h = int(target_client_h - final_client[1]) if final_client else 0
            logger.info(
                f"[resize][end] final_outer={self._cached_window.width}x{self._cached_window.height} "
                f"final_client={actual_client_text} err_client=({err_w},{err_h})"
            )

            logger.info(
                f"窗口客户区目标 {target_client_w}x{target_client_h}，"
                f"平台={platform}，dpi_scale={scale_percent}% (matched={matched_scale}%)，"
                f"累加: width+={width_add}, height+={height_add} "
                f"(border={border_width}, title={title_height})，"
                f"目标外框 {target_outer_w}x{target_outer_h}，"
                f"实际外框 {self._cached_window.width}x{self._cached_window.height}，"
                f"实际客户区 {actual_client_text}"
            )
            logger.info(
                f"窗口位置({self._cached_window.left},{self._cached_window.top}) [{position}]，{resize_msg}"
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
