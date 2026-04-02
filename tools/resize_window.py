import ctypes
import win32gui
import win32con
import time

def enable_dpi_awareness():
    """开启 DPI 感知，确保所有抓取和设置的坐标均为纯物理像素"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except AttributeError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def resize_window_physical(window_title, target_physical_w, target_physical_h, scale=1.5, app_type="QQ"):
    """
    调整窗口物理大小。
    新增逻辑：先缩小窗口强制重绘，再拉伸至目标分辨率。
    """
    # 1. 获取主窗口(父窗体)句柄
    main_hwnd = win32gui.FindWindow(None, window_title)
    if not main_hwnd:
        print(f"未找到名为 '{window_title}' 的窗口")
        return False

    # 2. 动态计算当前环境的“不可见边框”厚度
    rect_outer = win32gui.GetWindowRect(main_hwnd)
    outer_w = rect_outer[2] - rect_outer[0]
    outer_h = rect_outer[3] - rect_outer[1]

    rect_client = win32gui.GetClientRect(main_hwnd)
    client_w = rect_client[2] - rect_client[0]
    client_h = rect_client[3] - rect_client[1]

    border_w = outer_w - client_w
    border_h = outer_h - client_h

    # 3. 计算最终目标大小，以及用于触发重绘的“缩小版”大小
    # 这里将目标大小减半作为缩小尺寸，但设定了一个最低阈值(500x500)，防止触发窗口最小限制
    if app_type.lower() == "wechat" or app_type == "微信":
        print(f"---- 微信模式：间接调整 ----")
        final_parent_w = target_physical_w + border_w
        final_parent_h = target_physical_h + border_h
        
        small_parent_w = max(500, (target_physical_w // 2)) + border_w
        small_parent_h = max(500, (target_physical_h // 2)) + border_h
    else:
        print(f"---- QQ模式：直接调整 ----")
        final_parent_w = target_physical_w
        final_parent_h = target_physical_h
        
        small_parent_w = max(500, target_physical_w // 2)
        small_parent_h = max(500, target_physical_h // 2)

    flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_NOMOVE

    # 4. [步骤一] 先将窗口调整到一个较小的分辨率，强制破坏当前渲染缓存
    print(f"--> [步骤 1] 正在缩小窗口至 {small_parent_w}x{small_parent_h} 以强制刷新渲染引擎...")
    win32gui.SetWindowPos(
        main_hwnd,
        win32con.HWND_TOP,
        0, 0,  
        small_parent_w, small_parent_h,
        flags
    )

    # 给予 Chromium 引擎和系统 DWM 足够的时间去处理尺寸改变的消息并重绘
    # 通常 0.2 到 0.3 秒是一个非常稳定的黄金时间
    time.sleep(0.3)

    # 5. [步骤二] 设置为最终指定的分辨率
    print(f"--> [步骤 2] 正在拉伸至目标分辨率...")
    win32gui.SetWindowPos(
        main_hwnd,
        win32con.HWND_TOP,
        0, 0,  
        final_parent_w, final_parent_h,
        flags
    )
    
    print(f"窗口 '{window_title}' 已完成两段式调整！")
    print(f"最终生效的父窗体物理像素: {final_parent_w}x{final_parent_h}")
    print("-" * 30)
    return True

if __name__ == "__main__":
    enable_dpi_awareness()
    
    # 你的目标物理大小是 540+边框*2 * 960+边框*2+标题
    scale_factor = 1.5
    
    # 测试 QQ 分支
    # target_physical_width = 542
    # target_physical_height = 1001
    # resize_window_physical(
    #     "QQ经典农场", 
    #     target_physical_width, 
    #     target_physical_height, 
    #     scale=scale_factor, 
    #     app_type="QQ"
    # )

    # 测试 微信 分支
    target_physical_width = 540
    target_physical_height = 1026
    resize_window_physical(
        "QQ经典农场", 
        target_physical_width,
        target_physical_height,
        scale=scale_factor,
        app_type="wechat"
    )
