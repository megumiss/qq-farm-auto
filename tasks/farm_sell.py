"""出售任务。"""

from __future__ import annotations

from loguru import logger

from core.base.step_result import StepResult
from core.base.timer import Timer
from core.ui.assets import (
    BTN_BATCH_SELL,
    BTN_CLOSE,
    BTN_CONFIRM,
    MAIN_GOTO_WAREHOUSE,
    WAREHOUSE_CHECK,
)
from core.ui.page import page_main
from models.farm_state import ActionType


class TaskFarmSell:
    """封装 `TaskFarmSell` 任务的执行入口与步骤。"""

    def __init__(self, engine, ui):
        """初始化对象并准备运行所需状态。"""
        self.engine = engine
        self.ui = ui

    def run(self, features, sold_this_round: bool) -> tuple[StepResult, bool]:
        """执行当前模块主流程并返回结果。"""
        if sold_this_round or not features.get('auto_sell', False):
            return StepResult(), sold_this_round

        if not self._goto_warehouse():
            return StepResult(), sold_this_round

        sold = self._batch_sell_once()
        self._back_to_main()
        if not sold:
            return StepResult(), sold_this_round
        return StepResult.from_value('批量出售果实'), True

    def _goto_warehouse(self, skip_first_screenshot: bool = True) -> bool:
        """进入仓库页面。"""
        logger.info('sell: goto warehouse')
        confirm_timer = Timer(2.0, count=2).start()
        click_timer = Timer(0.3)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.ui.device.screenshot()

            if (
                self.ui.appear(WAREHOUSE_CHECK, offset=(30, 30), threshold=0.8, static=False)
                and confirm_timer.reached()
            ):
                return True

            if click_timer.reached() and self.ui.appear_then_click(
                MAIN_GOTO_WAREHOUSE, offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                confirm_timer.reset()
                click_timer.reset()
                continue

            if click_timer.reached() and self.ui.appear_then_click_any(
                [BTN_CLOSE, BTN_CONFIRM], offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                confirm_timer.reset()
                click_timer.reset()
                continue

            if self.ui.ui_additional():
                confirm_timer.reset()
                click_timer.reset()
                continue

            if confirm_timer.reached():
                return False

    def _batch_sell_once(self, skip_first_screenshot: bool = True) -> bool:
        """仓库内执行一次批量出售。"""
        logger.info('sell: batch sell')
        confirm_timer = Timer(2.0, count=3).start()
        click_timer = Timer(0.3)
        batch_clicked = False
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.ui.device.screenshot()

            if click_timer.reached() and self.ui.appear_then_click(
                BTN_BATCH_SELL, offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                batch_clicked = True
                confirm_timer.reset()
                click_timer.reset()
                continue

            if click_timer.reached() and self.ui.appear_then_click(
                BTN_CONFIRM, offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                self.engine._record_stat(ActionType.SELL)
                self.ui.device.sleep(0.2)
                return True

            if click_timer.reached() and self.ui.appear_then_click(
                BTN_CLOSE, offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                click_timer.reset()
                if batch_clicked:
                    return False
                continue

            if self.ui.ui_additional():
                confirm_timer.reset()
                click_timer.reset()
                continue

            if confirm_timer.reached():
                return False

    def _back_to_main(self, skip_first_screenshot: bool = True):
        """兜底返回主页面。"""
        logger.info('sell: back to main')
        confirm_timer = Timer(2.0, count=2).start()
        click_timer = Timer(0.3)
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.ui.device.screenshot()

            if self.ui.ui_page_appear(page_main) and confirm_timer.reached():
                return

            if click_timer.reached() and self.ui.appear_then_click_any(
                [BTN_CLOSE, BTN_CONFIRM], offset=(30, 30), interval=1, threshold=0.8, static=False
            ):
                confirm_timer.reset()
                click_timer.reset()
                continue

            if self.ui.ui_additional():
                confirm_timer.reset()
                click_timer.reset()
                continue

            if confirm_timer.reached():
                return
