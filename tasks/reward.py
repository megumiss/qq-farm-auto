"""任务奖励领取。"""

from __future__ import annotations

from core.engine.task.registry import TaskResult
from core.ui.assets import BTN_CLOSE, BTN_CONFIRM, BTN_DIRECT_CLAIM, TASK_CHECK
from core.ui.page import page_main
from tasks.base import TaskBase


class TaskReward(TaskBase):
    """封装 `TaskReward` 任务的执行入口与步骤。"""

    def __init__(self, engine, ui):
        """初始化对象并准备运行所需状态。"""
        super().__init__(engine, ui)

    def run(self, rect: tuple[int, int, int, int]) -> TaskResult:
        """执行任务奖励领取并返回调度结果。"""
        self.ui.ui_ensure(page_main)

        self._run_reward_flow()
        return self.ok()

    def _run_reward_flow(self):
        """执行任务奖励领取流程。"""
        if not self.ui.appear(TASK_CHECK, offset=(30, 30), threshold=0.85):
            return

        while 1:
            self.ui.device.screenshot()

            if self.ui.appear_then_click(BTN_DIRECT_CLAIM, offset=(30, 30), interval=1, threshold=0.8, static=False):
                return

            if self.ui.appear_then_click_any(
                [BTN_CLOSE, BTN_CONFIRM], offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                continue

        return
