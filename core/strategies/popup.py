"""P-1 异常处理 — 关闭弹窗/商店/任务奖励分享"""
import time
import pyautogui
from loguru import logger

from models.farm_state import ActionType
from core.cv_detector import DetectResult
from core.strategies.base import BaseStrategy


class PopupStrategy(BaseStrategy):

    def handle_popup(self, detections: list[DetectResult]) -> str | None:
        """处理弹窗：分享(双倍奖励) > 领取 > 确认 > 关闭 > 取消"""
        # 优先检测分享按钮（任务奖励弹窗，拿双倍）
        share_btn = self.find_by_name(detections, "btn_share")
        if share_btn:
            return self._share_and_cancel(share_btn)

        for btn_name in ["btn_claim", "btn_confirm", "btn_close", "btn_cancel"]:
            det = self.find_by_name(detections, btn_name)
            if det:
                label = btn_name.replace("btn_", "")
                self.click(det.x, det.y, f"关闭弹窗({label})", ActionType.CLOSE_POPUP)
                return f"关闭弹窗({label})"
        return None

    def _share_and_cancel(self, share_btn: DetectResult) -> str:
        """点分享 → 等微信窗口弹出 → 点取消 → 回游戏，拿双倍奖励

        微信分享窗口"取消"按钮在窗口右下角，位置相对固定。
        点取消后游戏不检测是否真的分享了，直接发放双倍奖励。
        """
        self.click(share_btn.x, share_btn.y, "点击分享(双倍奖励)", ActionType.CLOSE_POPUP)
        self.sleep(2.0)  # 等待微信分享窗口弹出

        # 按 Escape 关闭微信分享窗口（比找取消按钮更可靠）
        pyautogui.press("escape")
        self.sleep(1.0)  # 等待窗口关闭，回到游戏

        logger.info("任务奖励: 分享→取消，领取双倍奖励")
        return "领取双倍任务奖励"

    def close_shop(self, rect: tuple):
        """关闭商店页面"""
        for _ in range(3):
            cv_img, dets, _ = self.capture(rect)
            if cv_img is None:
                return
            shop_close = self.cv_detector.detect_single_template(
                cv_img, "btn_shop_close", threshold=0.8)
            close_btn = shop_close[0] if shop_close else self.find_by_name(dets, "btn_close")
            if close_btn:
                self.click(close_btn.x, close_btn.y, "关闭商店", ActionType.CLOSE_POPUP)
                self.sleep(0.3)
            else:
                return

