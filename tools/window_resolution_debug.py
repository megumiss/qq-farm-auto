"""Window resolution debug tool for Windows.

Usage examples:
  python tools/window_resolution_debug.py --title "QQ经典农场"
  python tools/window_resolution_debug.py --title "QQ经典农场" --width 540
  python tools/window_resolution_debug.py --title "QQ经典农场" --width 540 --height 960 --position left_center
  python tools/window_resolution_debug.py --title "QQ经典农场" --width 540 --height 960 --space physical
  python tools/window_resolution_debug.py --title "QQ经典农场" --check-rounds 5 --check-interval 0.5
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import time
from dataclasses import dataclass


GWL_STYLE = -16
GWL_EXSTYLE = -20
SPI_GETWORKAREA = 0x0030
DWMWA_EXTENDED_FRAME_BOUNDS = 9
SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOOWNERZORDER = 0x0200
SWP_FRAMECHANGED = 0x0020
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_CHILD = 0x40000000
WM_SIZE = 0x0005
SIZE_RESTORED = 0
RDW_INVALIDATE = 0x0001
RDW_ALLCHILDREN = 0x0080
RDW_UPDATENOW = 0x0100
WM_ENTERSIZEMOVE = 0x0231
WM_EXITSIZEMOVE = 0x0232
SW_HIDE = 0
SW_SHOW = 5
GA_PARENT = 1
GA_ROOT = 2
GA_ROOTOWNER = 3


# 微信
# 客户区 540 937 需要设置窗口 540 1003
# QQ
# 客户区 540 937 需要设置窗口 540 997


def set_process_dpi_awareness() -> str:
    """Try to opt this process into DPI-aware mode (compat with old/new Windows)."""
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE
        hr = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if hr == 0:
            return "SetProcessDpiAwareness(2):S_OK"
        return f"SetProcessDpiAwareness(2):HRESULT=0x{int(hr) & 0xFFFFFFFF:08X}"
    except Exception as exc:
        shcore_msg = f"SetProcessDpiAwareness exception: {exc}"
    try:
        ok = bool(ctypes.windll.user32.SetProcessDPIAware())
        if ok:
            return "SetProcessDPIAware():OK"
        return f"{shcore_msg}; SetProcessDPIAware():False"
    except Exception as exc:
        return f"{shcore_msg}; SetProcessDPIAware exception: {exc}"


def detect_virtualized_metrics(snap: "WindowSnapshot") -> bool:
    """Best-effort: detect if GetWindowRect-like metrics are DPI-virtualized."""
    if not snap.extended_frame_rect:
        return False
    if snap.window_rect.width <= 0 or snap.window_rect.height <= 0:
        return False
    expected_scale = dpi_scale_from_dpi(snap.dpi)
    if expected_scale <= 1.01:
        return False
    ratio_w = snap.extended_frame_rect.width / float(snap.window_rect.width)
    ratio_h = snap.extended_frame_rect.height / float(snap.window_rect.height)
    return abs(ratio_w - expected_scale) < 0.08 and abs(ratio_h - expected_scale) < 0.08


def logical_to_physical_by_snapshot(logical_w: int, logical_h: int, snap: "WindowSnapshot") -> tuple[int, int]:
    if detect_virtualized_metrics(snap):
        scale = dpi_scale_from_dpi(snap.dpi)
        return int(round(logical_w * scale)), int(round(logical_h * scale))
    return logical_w, logical_h


def physical_to_logical_by_snapshot(physical_w: int, physical_h: int, snap: "WindowSnapshot") -> tuple[int, int]:
    if detect_virtualized_metrics(snap):
        scale = dpi_scale_from_dpi(snap.dpi)
        return int(round(physical_w / scale)), int(round(physical_h / scale))
    return physical_w, physical_h


def actual_physical_size_from_snapshot(snap: "WindowSnapshot") -> tuple[int, int, str]:
    if snap.extended_frame_rect:
        return snap.extended_frame_rect.width, snap.extended_frame_rect.height, "extended_frame_rect"
    w, h = logical_to_physical_by_snapshot(snap.client_rect_screen.width, snap.client_rect_screen.height, snap)
    return w, h, "logical*dpi_scale_or_identity"


def actual_logical_size_from_snapshot(snap: "WindowSnapshot") -> tuple[int, int]:
    return snap.client_rect_screen.width, snap.client_rect_screen.height


def format_virtualization_hint(snap: "WindowSnapshot") -> str:
    return "virtualized" if detect_virtualized_metrics(snap) else "not_virtualized"


def dpi_scale_from_dpi(dpi: int) -> float:
    return float(dpi) / 96.0


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass
class WindowSnapshot:
    hwnd: int
    title: str
    class_name: str
    dpi: int
    style: int
    ex_style: int
    window_rect: Rect
    client_rect_screen: Rect
    extended_frame_rect: Rect | None
    visible: bool
    foreground: bool
    zoomed: bool
    iconic: bool
    resizable: bool
    has_maximize_box: bool
    has_minimize_box: bool
    is_child_window: bool
    parent_hwnd: int
    root_hwnd: int
    root_owner_hwnd: int


@dataclass
class ChildWindowInfo:
    hwnd: int
    class_name: str
    rect: Rect
    visible: bool


def _load_pygetwindow():
    try:
        import pygetwindow as gw
    except Exception:
        print("Missing dependency: pygetwindow. Please install requirements first.")
        return None
    return gw


def list_candidate_windows(title_keyword: str) -> list[tuple[int, str, int, int]]:
    gw = _load_pygetwindow()
    if gw is None:
        return []

    candidates: list[tuple[int, str, int, int]] = []
    keyword_lower = title_keyword.lower()
    for win in gw.getAllWindows():
        if not win.title:
            continue
        title_lower = win.title.lower()
        if keyword_lower in title_lower or all(k in title_lower for k in keyword_lower.split()):
            candidates.append((int(win._hWnd), win.title, int(win.width), int(win.height)))
    return candidates


def find_window(title_keyword: str) -> tuple[int, str] | None:
    gw = _load_pygetwindow()
    if gw is None:
        pass
        return None

    windows = gw.getWindowsWithTitle(title_keyword)
    if not windows:
        keyword_lower = title_keyword.lower()
        for win in gw.getAllWindows():
            title = win.title.lower()
            if keyword_lower in title or all(k in title for k in keyword_lower.split()):
                windows = [win]
                break
    if not windows:
        for win in gw.getAllWindows():
            if "农场" in win.title:
                windows = [win]
                break
    if not windows:
        return None

    target = windows[0]
    return int(target._hWnd), target.title


def _get_window_rect(hwnd: int) -> Rect | None:
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    ok = user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if not ok:
        return None
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


def _get_client_rect_screen(hwnd: int) -> Rect | None:
    user32 = ctypes.windll.user32
    rect = ctypes.wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None

    pt = ctypes.wintypes.POINT(0, 0)
    if not user32.ClientToScreen(hwnd, ctypes.byref(pt)):
        return None

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    return Rect(pt.x, pt.y, pt.x + width, pt.y + height)


def _get_extended_frame_bounds(hwnd: int) -> Rect | None:
    try:
        dwmapi = ctypes.windll.dwmapi
    except Exception:
        return None

    rect = ctypes.wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        ctypes.wintypes.HWND(hwnd),
        ctypes.wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if hr != 0:
        return None
    return Rect(rect.left, rect.top, rect.right, rect.bottom)


def _get_dpi(hwnd: int) -> int:
    user32 = ctypes.windll.user32
    try:
        return int(user32.GetDpiForWindow(hwnd))
    except Exception:
        return 96


def _get_class_name(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 255)
    return buf.value


def _enum_child_windows(hwnd: int) -> list[int]:
    user32 = ctypes.windll.user32
    child_hwnds: list[int] = []

    enum_proc = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    @enum_proc
    def _callback(child_hwnd, _lparam):
        child_hwnds.append(int(child_hwnd))
        return True

    user32.EnumChildWindows(hwnd, _callback, 0)
    return child_hwnds


def _get_ancestor(hwnd: int, flag: int) -> int:
    user32 = ctypes.windll.user32
    try:
        return int(user32.GetAncestor(hwnd, flag))
    except Exception:
        return 0


def resolve_operation_hwnd(hwnd: int, target: str) -> int:
    if target == "root":
        return _get_ancestor(hwnd, GA_ROOT) or hwnd
    if target == "root_owner":
        return _get_ancestor(hwnd, GA_ROOTOWNER) or hwnd
    return hwnd


def _format_hwnd_with_class(hwnd: int) -> str:
    if not hwnd:
        return "0x0"
    return f"0x{hwnd:X}({_get_class_name(hwnd)})"


def _collect_child_window_info(hwnd: int) -> list[ChildWindowInfo]:
    infos: list[ChildWindowInfo] = []
    user32 = ctypes.windll.user32
    for child in _enum_child_windows(hwnd):
        rect = _get_window_rect(child)
        if not rect:
            continue
        infos.append(
            ChildWindowInfo(
                hwnd=child,
                class_name=_get_class_name(child),
                rect=rect,
                visible=bool(user32.IsWindowVisible(child)),
            )
        )
    return infos


def _calculate_position(
    work_area: ctypes.wintypes.RECT, window_width: int, window_height: int, position: str
) -> tuple[int, int]:
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
        x = wa_left
        y = wa_top + (wa_height - window_height) // 2

    x = max(wa_left, min(x, wa_right - window_width))
    y = max(wa_top, min(y, wa_bottom - window_height))
    return x, y


def capture_window_snapshot(hwnd: int, title: str) -> WindowSnapshot | None:
    user32 = ctypes.windll.user32
    window_rect = _get_window_rect(hwnd)
    client_rect_screen = _get_client_rect_screen(hwnd)
    if not window_rect or not client_rect_screen:
        return None

    style = int(user32.GetWindowLongW(hwnd, GWL_STYLE))
    ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    dpi = _get_dpi(hwnd)
    visible = bool(user32.IsWindowVisible(hwnd))
    foreground = int(user32.GetForegroundWindow()) == int(hwnd)
    zoomed = bool(user32.IsZoomed(hwnd))
    iconic = bool(user32.IsIconic(hwnd))

    return WindowSnapshot(
        hwnd=hwnd,
        title=title,
        class_name=_get_class_name(hwnd),
        dpi=dpi,
        style=style,
        ex_style=ex_style,
        window_rect=window_rect,
        client_rect_screen=client_rect_screen,
        extended_frame_rect=_get_extended_frame_bounds(hwnd),
        visible=visible,
        foreground=foreground,
        zoomed=zoomed,
        iconic=iconic,
        resizable=bool(style & WS_THICKFRAME),
        has_maximize_box=bool(style & WS_MAXIMIZEBOX),
        has_minimize_box=bool(style & WS_MINIMIZEBOX),
        is_child_window=bool(style & WS_CHILD),
        parent_hwnd=_get_ancestor(hwnd, GA_PARENT),
        root_hwnd=_get_ancestor(hwnd, GA_ROOT),
        root_owner_hwnd=_get_ancestor(hwnd, GA_ROOTOWNER),
    )


def activate_window(hwnd: int) -> tuple[bool, str]:
    user32 = ctypes.windll.user32
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd))
        if not ok:
            return False, "SetForegroundWindow returned false."
        return True, "Window activated."
    except Exception as exc:
        return False, f"activate failed: {exc}"


def print_snapshot(title: str, snap: WindowSnapshot) -> None:
    scale = dpi_scale_from_dpi(snap.dpi)
    physical_client_w, physical_client_h, physical_source = actual_physical_size_from_snapshot(snap)
    print(f"\n=== {title} ===")
    print(f"hwnd: {snap.hwnd} (0x{snap.hwnd:X})")
    print(f"title: {snap.title}")
    print(f"class: {snap.class_name}")
    print(f"dpi: {snap.dpi}")
    print(f"dpi_scale: {scale:.3f}")
    print(f"style: 0x{snap.style:08X}")
    print(f"ex_style: 0x{snap.ex_style:08X}")
    print(f"visible: {snap.visible}")
    print(f"foreground: {snap.foreground}")
    print(f"zoomed(maximized): {snap.zoomed}")
    print(f"iconic(minimized): {snap.iconic}")
    print(f"resizable(WS_THICKFRAME): {snap.resizable}")
    print(f"has_maximize_box: {snap.has_maximize_box}")
    print(f"has_minimize_box: {snap.has_minimize_box}")
    print(f"is_child_window: {snap.is_child_window}")
    print(f"ancestor_parent: {_format_hwnd_with_class(snap.parent_hwnd)}")
    print(f"ancestor_root: {_format_hwnd_with_class(snap.root_hwnd)}")
    print(f"ancestor_root_owner: {_format_hwnd_with_class(snap.root_owner_hwnd)}")
    print(
        f"window_rect: L{snap.window_rect.left} T{snap.window_rect.top} "
        f"R{snap.window_rect.right} B{snap.window_rect.bottom} "
        f"(W={snap.window_rect.width}, H={snap.window_rect.height})"
    )
    print(
        f"client_rect(screen): L{snap.client_rect_screen.left} T{snap.client_rect_screen.top} "
        f"R{snap.client_rect_screen.right} B{snap.client_rect_screen.bottom} "
        f"(W={snap.client_rect_screen.width}, H={snap.client_rect_screen.height})"
    )
    print(
        f"client_estimated_physical: {physical_client_w}x{physical_client_h} "
        f"(source={physical_source})"
    )
    print(f"metric_virtualization: {format_virtualization_hint(snap)}")
    if snap.extended_frame_rect:
        ef = snap.extended_frame_rect
        print(
            f"extended_frame_rect: L{ef.left} T{ef.top} R{ef.right} B{ef.bottom} "
            f"(W={ef.width}, H={ef.height})"
        )
    else:
        print("extended_frame_rect: unavailable")


def set_window_client_resolution(
    hwnd: int,
    target_client_width: int,
    target_client_height: int,
    position: str,
    prefer_measured_nonclient: bool = True,
) -> tuple[bool, str]:
    user32 = ctypes.windll.user32
    window_rect = _get_window_rect(hwnd)
    client_rect = _get_client_rect_screen(hwnd)
    if not window_rect or not client_rect:
        return False, "Failed to read current window/client rect."
    class_name = _get_class_name(hwnd)

    # Some host windows report client area == window rect. In this mode,
    # applying AdjustWindowRectEx(ForDpi) over-compensates and causes overshoot.
    same_window_and_client = (
        window_rect.left == client_rect.left
        and window_rect.top == client_rect.top
        and window_rect.width == client_rect.width
        and window_rect.height == client_rect.height
    )

    if same_window_and_client:
        target_window_width = int(target_client_width)
        target_window_height = int(target_client_height)
        sizing_mode = "direct_client_equals_window"
    else:
        nonclient_w = max(0, int(window_rect.width - client_rect.width))
        nonclient_h = max(0, int(window_rect.height - client_rect.height))
        measured_w = int(target_client_width + nonclient_w)
        measured_h = int(target_client_height + nonclient_h)

        style = int(user32.GetWindowLongW(hwnd, GWL_STYLE))
        ex_style = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))

        rect = ctypes.wintypes.RECT(0, 0, int(target_client_width), int(target_client_height))
        adjusted = False

        try:
            dpi = int(user32.GetDpiForWindow(hwnd))
            adjusted = bool(
                user32.AdjustWindowRectExForDpi(
                    ctypes.byref(rect), style, False, ex_style, dpi
                )
            )
        except Exception:
            adjusted = False

        if not adjusted:
            ok = user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style)
            if not ok:
                return False, "AdjustWindowRectEx failed."

        adjusted_w = int(rect.right - rect.left)
        adjusted_h = int(rect.bottom - rect.top)

        # Chromium host windows often use custom non-client metrics.
        # Measured delta is usually more reliable than AdjustWindowRectExForDpi.
        use_measured = False
        if prefer_measured_nonclient:
            if class_name.startswith("Chrome_WidgetWin_"):
                use_measured = True
            elif abs(adjusted_h - measured_h) >= 12 or abs(adjusted_w - measured_w) >= 12:
                use_measured = True

        if use_measured:
            target_window_width = measured_w
            target_window_height = measured_h
            sizing_mode = "measured_nonclient_delta"
        else:
            target_window_width = adjusted_w
            target_window_height = adjusted_h
            sizing_mode = "adjust_window_rect"

    work_area = ctypes.wintypes.RECT()
    if not user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(work_area), 0):
        return False, "SystemParametersInfoW(SPI_GETWORKAREA) failed."

    x, y = _calculate_position(work_area, target_window_width, target_window_height, position)

    # Prefer SetWindowPos; fallback to MoveWindow for compatibility.
    ok = bool(
        user32.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            int(target_window_width),
            int(target_window_height),
            SWP_NOZORDER | SWP_NOOWNERZORDER,
        )
    )
    if ok:
        return True, (
            f"SetWindowPos succeeded. mode={sizing_mode}, "
            f"target_window={target_window_width}x{target_window_height}"
        )

    ok = bool(
        user32.MoveWindow(hwnd, int(x), int(y), int(target_window_width), int(target_window_height), True)
    )
    if ok:
        return True, (
            f"MoveWindow succeeded (SetWindowPos failed). mode={sizing_mode}, "
            f"target_window={target_window_width}x{target_window_height}"
        )
    return False, "SetWindowPos and MoveWindow both failed."


def tune_client_size_after_resize(
    hwnd: int,
    target_client_width: int,
    target_client_height: int,
    tune_width: bool,
    tune_height: bool,
    max_rounds: int = 6,
) -> tuple[bool, str]:
    """Iteratively correct window outer size by client-size error."""
    user32 = ctypes.windll.user32
    if not tune_width and not tune_height:
        return True, "tune skipped: no dimension selected"

    for round_idx in range(1, max_rounds + 1):
        win_rect = _get_window_rect(hwnd)
        cli_rect = _get_client_rect_screen(hwnd)
        if not win_rect or not cli_rect:
            return False, f"tune failed at round {round_idx}: cannot read rects"

        err_w = int(target_client_width - cli_rect.width) if tune_width else 0
        err_h = int(target_client_height - cli_rect.height) if tune_height else 0
        if err_w == 0 and err_h == 0:
            return True, f"tune success in {round_idx - 1} rounds"

        next_w = max(120, int(win_rect.width + err_w))
        next_h = max(120, int(win_rect.height + err_h))

        ok = bool(
            user32.SetWindowPos(
                hwnd,
                0,
                int(win_rect.left),
                int(win_rect.top),
                int(next_w),
                int(next_h),
                SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED,
            )
        )
        if not ok:
            return False, f"tune failed at round {round_idx}: SetWindowPos failed"
        time.sleep(0.03)

    final_cli = _get_client_rect_screen(hwnd)
    if not final_cli:
        return False, "tune finished: cannot read final client rect"
    return False, (
        "tune reached max rounds; "
        f"final_client={final_cli.width}x{final_cli.height}, "
        f"target={target_client_width}x{target_client_height}"
    )


def force_layout_refresh(
    hwnd: int,
    width: int,
    height: int,
    jitter: int = 12,
    drag_delta: int = 96,
    drag_steps: int = 8,
) -> tuple[bool, str]:
    """Force host UI layout to refresh after resize (for embedded render surfaces)."""
    user32 = ctypes.windll.user32
    window_rect = _get_window_rect(hwnd)
    if not window_rect:
        return False, "force_layout_refresh: failed to read window rect"
    x, y = window_rect.left, window_rect.top
    jitter = max(2, int(jitter))
    drag_delta = max(jitter, int(drag_delta))
    drag_steps = max(2, int(drag_steps))
    child_hwnds = _enum_child_windows(hwnd)

    # 1) Simulate interactive resize lifecycle.
    user32.SendMessageW(hwnd, WM_ENTERSIZEMOVE, 0, 0)

    # 2) Progressive resize path to emulate manual dragging.
    start_w = int(width + drag_delta)
    start_h = int(height + drag_delta)
    ok1 = bool(
        user32.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            start_w,
            start_h,
            SWP_NOZORDER | SWP_NOOWNERZORDER,
        )
    )
    step_ok_count = 0
    for i in range(1, drag_steps + 1):
        w_i = int(start_w - (start_w - int(width)) * i / drag_steps)
        h_i = int(start_h - (start_h - int(height)) * i / drag_steps)
        if user32.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            w_i,
            h_i,
            SWP_NOZORDER | SWP_NOOWNERZORDER,
        ):
            step_ok_count += 1
        time.sleep(0.02)

    # 3) Final settle with frame changed.
    ok2 = bool(
        user32.SetWindowPos(
            hwnd,
            0,
            int(x),
            int(y),
            int(width),
            int(height),
            SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED,
        )
    )

    # 4) Explicit size + redraw notifications (parent + children).
    lparam = (int(height) << 16) | (int(width) & 0xFFFF)
    user32.SendMessageW(hwnd, WM_SIZE, SIZE_RESTORED, lparam)
    redraw_parent_ok = bool(
        user32.RedrawWindow(hwnd, None, None, RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW)
    )

    children_redraw_ok = 0
    for child in child_hwnds:
        child_client = _get_client_rect_screen(child)
        if child_client:
            cw, ch = child_client.width, child_client.height
            clparam = (int(ch) << 16) | (int(cw) & 0xFFFF)
            user32.SendMessageW(child, WM_SIZE, SIZE_RESTORED, clparam)
        if user32.RedrawWindow(child, None, None, RDW_INVALIDATE | RDW_UPDATENOW):
            children_redraw_ok += 1

    user32.SendMessageW(hwnd, WM_EXITSIZEMOVE, 0, 0)
    user32.UpdateWindow(hwnd)

    if ok1 and ok2 and redraw_parent_ok:
        return True, (
            "force_layout_refresh: entersize/progressive-drag/exitsize done, "
            f"step_ok={step_ok_count}/{drag_steps}, children={len(child_hwnds)}, "
            f"children_redraw_ok={children_redraw_ok}"
        )
    return False, (
        "force_layout_refresh partial: "
        f"jitter1={ok1}, step_ok={step_ok_count}/{drag_steps}, jitter2={ok2}, redraw_parent={redraw_parent_ok}, "
        f"children={len(child_hwnds)}, children_redraw_ok={children_redraw_ok}"
    )


def force_resize_children_to_parent_client(hwnd: int) -> tuple[bool, str]:
    """Resize child windows to fill parent client area to trigger embedded renderer relayout."""
    user32 = ctypes.windll.user32
    client = _get_client_rect_screen(hwnd)
    if not client:
        return False, "force_resize_children: failed to read parent client rect"
    target_w, target_h = client.width, client.height
    resized = 0
    considered = 0
    details: list[str] = []

    for child in _collect_child_window_info(hwnd):
        if not child.visible:
            continue
        considered += 1
        # Skip tiny helper controls; prioritize render/content windows.
        if child.rect.width < 80 or child.rect.height < 80:
            continue
        ok = bool(
            user32.SetWindowPos(
                child.hwnd,
                0,
                0,
                0,
                int(target_w),
                int(target_h),
                SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED,
            )
        )
        if ok:
            resized += 1
            details.append(f"0x{child.hwnd:X}:{child.class_name}")
            if child.class_name == "Chrome_RenderWidgetHostHWND":
                # Toggle visibility to force render host relayout/rebind.
                user32.ShowWindow(child.hwnd, SW_HIDE)
                time.sleep(0.01)
                user32.ShowWindow(child.hwnd, SW_SHOW)
            user32.SendMessageW(child.hwnd, WM_SIZE, SIZE_RESTORED, (int(target_h) << 16) | (int(target_w) & 0xFFFF))
            user32.RedrawWindow(child.hwnd, None, None, RDW_INVALIDATE | RDW_UPDATENOW)

    if resized > 0:
        preview = ", ".join(details[:4])
        return True, f"force_resize_children: resized={resized}/{considered}, sample=[{preview}]"
    return False, f"force_resize_children: resized=0/{considered}"


def check_resolution(
    snap: WindowSnapshot,
    expected_logical_width: int,
    expected_logical_height: int,
    expected_physical_width: int,
    expected_physical_height: int,
    check_space: str,
    check_width: bool = True,
    check_height: bool = True,
) -> tuple[bool, str]:
    actual_logical_w, actual_logical_h = actual_logical_size_from_snapshot(snap)
    actual_physical_w, actual_physical_h, physical_source = actual_physical_size_from_snapshot(snap)

    if check_space == "physical":
        width_match = (actual_physical_w == expected_physical_width) if check_width else True
        height_match = (actual_physical_h == expected_physical_height) if check_height else True
        match = width_match and height_match
        message = (
            f"check_space=physical, target={expected_physical_width}x{expected_physical_height}, "
            f"actual={actual_physical_w}x{actual_physical_h}, "
            f"delta=({actual_physical_w - expected_physical_width}, {actual_physical_h - expected_physical_height}); "
            f"check_mask=(w:{check_width},h:{check_height}); "
            f"logical={actual_logical_w}x{actual_logical_h}; source={physical_source}; "
            f"virtualization={format_virtualization_hint(snap)}"
        )
        return match, message

    width_match = (actual_logical_w == expected_logical_width) if check_width else True
    height_match = (actual_logical_h == expected_logical_height) if check_height else True
    match = width_match and height_match
    message = (
        f"check_space=logical, target={expected_logical_width}x{expected_logical_height}, "
        f"actual={actual_logical_w}x{actual_logical_h}, "
        f"delta=({actual_logical_w - expected_logical_width}, {actual_logical_h - expected_logical_height}); "
        f"check_mask=(w:{check_width},h:{check_height}); "
        f"physical={actual_physical_w}x{actual_physical_h}; source={physical_source}; "
        f"virtualization={format_virtualization_hint(snap)}"
    )
    return match, message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Debug and verify window resolution.")
    parser.add_argument("--title", default="QQ经典农场", help="Window title keyword.")
    parser.add_argument("--hwnd", default="", help="Directly target hwnd (hex like 0x12345 or decimal).")
    parser.add_argument("--width", type=int, default=None, help="Target client width.")
    parser.add_argument("--height", type=int, default=None, help="Target client height.")
    parser.add_argument(
        "--target",
        choices=["self", "root", "root_owner"],
        default="self",
        help="Which hwnd layer to operate on.",
    )
    parser.add_argument(
        "--space",
        choices=["logical", "physical"],
        default="logical",
        help="Interpret --width/--height as logical (DIP) or physical pixels.",
    )
    parser.add_argument(
        "--position",
        choices=["left_center", "center", "right_center", "top_left", "top_right"],
        default="left_center",
        help="Window target position in work area.",
    )
    parser.add_argument("--check-rounds", type=int, default=3, help="How many post-check rounds.")
    parser.add_argument("--check-interval", type=float, default=0.5, help="Seconds between checks.")
    parser.add_argument("--dry-run", action="store_true", help="Only print current info, do not resize.")
    parser.add_argument("--list", action="store_true", help="List candidate windows by --title and exit.")
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Do not activate window before resize/check.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dpi_awareness_mode = set_process_dpi_awareness()
    print(f"dpi_awareness: {dpi_awareness_mode}")

    if args.list:
        candidates = list_candidate_windows(args.title)
        if not candidates:
            print(f"No candidate windows found by keyword: {args.title}")
            return 1
        print("Candidates:")
        for i, item in enumerate(candidates, start=1):
            hwnd, title, width, height = item
            print(f"  {i:02d}. hwnd=0x{hwnd:X} size={width}x{height} title={title}")
        return 0

    hwnd: int
    title: str
    if args.hwnd:
        hwnd = int(args.hwnd, 0)
        title = f"hwnd=0x{hwnd:X}"
    else:
        found = find_window(args.title)
        if not found:
            print(f"Window not found by keyword: {args.title}")
            print("Tip: run with --list first, then pass --hwnd to target exact window.")
            return 1
        hwnd, title = found

    print(f"Window found: {title} (hwnd=0x{hwnd:X})")

    if not args.no_activate:
        activated, activate_msg = activate_window(hwnd)
        print(f"activate_result: {activated}, {activate_msg}")
        time.sleep(0.2)

    before = capture_window_snapshot(hwnd, title)
    if not before:
        print("Failed to capture window info before resize.")
        return 1
    print_snapshot("BEFORE", before)
    op_hwnd = resolve_operation_hwnd(hwnd, args.target)
    print(
        "operation_target: "
        f"{args.target} -> 0x{op_hwnd:X} ({_get_class_name(op_hwnd) if op_hwnd else 'N/A'})"
    )
    child_infos = _collect_child_window_info(op_hwnd)
    if child_infos:
        print(f"child_windows(on_operation_target): total={len(child_infos)}")
        for child in child_infos[:8]:
            print(
                f"  child hwnd=0x{child.hwnd:X} class={child.class_name} "
                f"visible={child.visible} size={child.rect.width}x{child.rect.height}"
            )

    width_provided = args.width is not None
    height_provided = args.height is not None

    current_logical_w, current_logical_h = actual_logical_size_from_snapshot(before)
    current_physical_w, current_physical_h, _ = actual_physical_size_from_snapshot(before)

    if not width_provided and not height_provided:
        # Keep historical default when both are omitted.
        target_input_w = 540
        target_input_h = 960
        mode_label = "default_540x960"
        check_width = True
        check_height = True
    else:
        if args.space == "physical":
            target_input_w = int(args.width) if width_provided else int(current_physical_w)
            target_input_h = int(args.height) if height_provided else int(current_physical_h)
        else:
            target_input_w = int(args.width) if width_provided else int(current_logical_w)
            target_input_h = int(args.height) if height_provided else int(current_logical_h)
        if width_provided and not height_provided:
            mode_label = "width_only"
        elif height_provided and not width_provided:
            mode_label = "height_only"
        else:
            mode_label = "width_height"
        check_width = width_provided
        check_height = height_provided

    if args.space == "physical":
        set_logical_width, set_logical_height = physical_to_logical_by_snapshot(
            int(target_input_w), int(target_input_h), before
        )
    else:
        set_logical_width = int(target_input_w)
        set_logical_height = int(target_input_h)

    print(
        "target_input: "
        f"{target_input_w}x{target_input_h} ({args.space}, mode={mode_label}), "
        f"target_set_logical: {set_logical_width}x{set_logical_height}, "
        f"check_mask=(w:{check_width},h:{check_height})"
    )

    if not args.dry_run:
        ok, msg = set_window_client_resolution(op_hwnd, set_logical_width, set_logical_height, args.position)
        print(f"\nResize result: {ok}, {msg}")
        if not ok:
            return 2
        tune_ok, tune_msg = tune_client_size_after_resize(
            op_hwnd,
            target_client_width=set_logical_width,
            target_client_height=set_logical_height,
            tune_width=True,
            tune_height=True,
        )
        print(f"post_resize_tune_result: {tune_ok}, {tune_msg}")
    else:
        print("\nDry run mode: resize skipped.")

    for i in range(1, max(1, args.check_rounds) + 1):
        if i > 1:
            time.sleep(max(0.0, args.check_interval))

        snap = capture_window_snapshot(hwnd, title)
        if not snap:
            print(f"\nCHECK #{i}: failed to capture window snapshot.")
            return 3

        print_snapshot(f"CHECK #{i}", snap)
        if op_hwnd != hwnd:
            op_snap = capture_window_snapshot(op_hwnd, f"operation_target=0x{op_hwnd:X}")
            if op_snap:
                print_snapshot(f"CHECK #{i} (OP_TARGET)", op_snap)
        matched, detail = check_resolution(
            snap=snap,
            expected_logical_width=set_logical_width,
            expected_logical_height=set_logical_height,
            expected_physical_width=int(target_input_w) if args.space == "physical" else logical_to_physical_by_snapshot(set_logical_width, set_logical_height, snap)[0],
            expected_physical_height=int(target_input_h) if args.space == "physical" else logical_to_physical_by_snapshot(set_logical_width, set_logical_height, snap)[1],
            check_space=args.space,
            check_width=check_width,
            check_height=check_height,
        )
        print(f"resolution_check: {'PASS' if matched else 'FAIL'} - {detail}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
