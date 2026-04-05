"""好友求助任务。"""

from __future__ import annotations

from core.base.step_result import StepResult
from core.ui.assets import (
    ASSET_NAME_TO_CONST,
    BTN_BUG,
    BTN_CLAIM,
    BTN_CLOSE,
    BTN_CONFIRM,
    BTN_HOME,
    BTN_WATER,
    BTN_WEED,
)

# TODO: `btn_friend_help` asset 已删除，当前“好友求助入口”步骤会被跳过。
BTN_FRIEND_HELP = ASSET_NAME_TO_CONST.get('btn_friend_help')


class TaskFarmFriend:
    """封装 `TaskFarmFriend` 任务的执行入口与步骤。"""

    def __init__(self, engine, ui):
        """初始化对象并准备运行所需状态。"""
        self.engine = engine
        self.ui = ui

    def run(self, rect, features) -> StepResult:
        """执行当前模块主流程并返回结果。"""
        if not features.get('auto_help', False):
            return StepResult()
        if BTN_FRIEND_HELP is None:
            return StepResult()
        if not self.ui.appear_then_click(BTN_FRIEND_HELP, offset=(30, 30), interval=1, threshold=0.8, static=False):
            return StepResult()
        self.ui.device.sleep(0.4)
        out = StepResult.from_value(self.help_in_friend_farm(rect))
        return out

    def help_in_friend_farm(self, rect: tuple[int, int, int, int]) -> list[str]:
        """在好友农场执行浇水/除草/除虫，完成后尝试回家。"""
        actions_done: list[str] = []
        idle_rounds = 0

        for _ in range(12):
            cv_img = self.ui.device.screenshot(rect=rect, save=False)
            if cv_img is None:
                break

            acted = False
            for btn, desc in [
                (BTN_WATER, '帮好友浇水'),
                (BTN_WEED, '帮好友除草'),
                (BTN_BUG, '帮好友除虫'),
            ]:
                if not self.ui.appear_then_click(btn, offset=(30, 30), interval=1, threshold=0.8, static=False):
                    continue
                actions_done.append(desc)
                acted = True
                self.ui.device.sleep(0.3)
                break

            if acted:
                idle_rounds = 0
                continue

            if self.ui.appear_then_click(BTN_HOME, offset=(30, 30), interval=1, threshold=0.8, static=False):
                actions_done.append('回家')
                self.ui.device.sleep(0.3)
                break

            if self.ui.appear_then_click_any(
                [BTN_CLAIM, BTN_CONFIRM, BTN_CLOSE], offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                self.ui.device.sleep(0.2)
                continue

            idle_rounds += 1
            if idle_rounds >= 2:
                break
            self.ui.device.sleep(0.2)

        return actions_done


