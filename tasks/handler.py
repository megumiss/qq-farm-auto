"""nklite 全局弹窗/异常处理。"""

from __future__ import annotations

from core.base.module_base import ModuleBase
from core.exceptions import LoginRepeatError
from core.ui.assets import BTN_CLICK_TO_CLOSE, BTN_CLOSE, BTN_COME_AGAIN


class Handler(ModuleBase):
    """封装 `Handler` 相关的数据与行为。"""

    def handle_click_close(self):
        """点击空白处关闭"""
        if self.appear_then_click(BTN_CLICK_TO_CLOSE, offset=30, interval=1, static=False):
            return True

    def handle_announcement(self):
        """执行 `handle announcement` 相关处理。"""
        return self.appear_then_click(BTN_CLOSE, offset=(30, 30), interval=1, threshold=0.8, static=False)

    def handle_login_repeat(self):
        """QQ重复登录"""
        if self.appear(BTN_COME_AGAIN, offset=30, static=False):
            raise LoginRepeatError
