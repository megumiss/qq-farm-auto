"""P3 任务 — 点击任务条，自动领取奖励或执行子任务（如售卖果实）

流程：
  检测 btn_task（左下角任务条）→ 点击 →
    - 任务奖励弹窗 → 分享领双倍 / 直接领取
    - 仓库页面（售卖任务）→ 批量出售
    - 其他弹窗 → 关闭

需要模板：
  btn_task          — 左下角任务提示条
  btn_batch_sell    — 仓库"批量出售"按钮
"""
import time
import pyautogui
from loguru import logger

from models.farm_state import ActionType
from core.cv_detector import DetectResult
from core.strategies.base import BaseStrategy


class TaskStrategy(BaseStrategy):

    def __init__(self, cv_detector):
        super().__init__(cv_detector)
        self.sell_config = None  # 由 bot_engine 设置

    def try_task(self, rect: tuple, detections: list[DetectResult]) -> list[str]:
        """检测任务条并执行"""
        btn = self.find_by_name(detections, "btn_task")
        if not btn:
            return []

        self.click(btn.x, btn.y, "点击任务")
        time.sleep(1.0)  # 等待任务弹窗或页面跳转

        return self._handle_task_result(rect)

    def _handle_task_result(self, rect: tuple) -> list[str]:
        """根据点击任务后的页面判断执行什么"""
        actions = []

        for attempt in range(5):
            if self.stopped:
                return actions
            cv_img, dets, _ = self.capture(rect)
            if cv_img is None:
                return actions

            names = {d.name for d in dets}

            # 任务奖励弹窗 → 分享或领取（由 popup 策略处理）
            if {"btn_share", "btn_claim"} & names:
                share = self.find_by_name(dets, "btn_share")
                if share:
                    self._share_and_cancel(share)
                    actions.append("领取双倍任务奖励")
                else:
                    claim = self.find_by_name(dets, "btn_claim")
                    if claim:
                        self.click(claim.x, claim.y, "直接领取", ActionType.CLOSE_POPUP)
                        actions.append("领取任务奖励")
                time.sleep(0.5)
                return actions

            # 仓库页面（售卖任务）→ 批量出售
            batch_sell = self.cv_detector.detect_single_template(
                cv_img, "btn_batch_sell", threshold=0.8)
            if batch_sell:
                sell_actions = self._batch_sell(rect)
                actions.extend(sell_actions)
                return actions

            # 其他弹窗 → 关闭
            close = self.find_any(dets, ["btn_close", "btn_confirm", "btn_cancel"])
            if close:
                self.click(close.x, close.y, "关闭弹窗", ActionType.CLOSE_POPUP)
                return actions

            time.sleep(0.3)

        return actions

    def _share_and_cancel(self, share_btn: DetectResult):
        """点分享 → 按 Escape 关闭微信窗口 → 拿双倍奖励"""
        self.click(share_btn.x, share_btn.y, "点击分享(双倍奖励)", ActionType.CLOSE_POPUP)
        time.sleep(2.0)  # 等待微信分享窗口弹出
        pyautogui.press("escape")
        time.sleep(1.0)  # 等待回到游戏
        logger.info("任务: 分享→取消，领取双倍奖励")

    def _batch_sell(self, rect: tuple) -> list[str]:
        """批量出售：点批量出售 → 自动全选 → 点确认"""
        cv_img, dets, _ = self.capture(rect)
        if cv_img is None:
            return []
        batch_btn = self.cv_detector.detect_single_template(
            cv_img, "btn_batch_sell", threshold=0.8)
        if not batch_btn:
            return []

        self.click(batch_btn[0].x, batch_btn[0].y, "批量出售")
        time.sleep(0.5)  # 等待全选动画

        for attempt in range(3):
            if self.stopped:
                return []
            cv_img, dets, _ = self.capture(rect)
            if cv_img is None:
                return []
            confirm = self.cv_detector.detect_single_template(
                cv_img, "btn_confirm", threshold=0.8)
            if confirm:
                self.click(confirm[0].x, confirm[0].y, "确认出售", ActionType.SELL)
                logger.info("任务: 批量出售完成")
                time.sleep(0.5)  # 等待出售动画
                self._close_page(rect)
                return ["批量出售果实"]
            time.sleep(0.3)

        logger.warning("任务: 未找到出售确认按钮")
        self._close_page(rect)
        return []

    def _close_page(self, rect: tuple):
        """关闭当前页面"""
        cv_img, dets, _ = self.capture(rect)
        if cv_img is None:
            return
        close = self.find_any(dets, ["btn_close", "btn_shop_close"])
        if close:
            self.click(close.x, close.y, "关闭页面", ActionType.CLOSE_POPUP)
            time.sleep(0.3)
