"""P0 收益 — 一键收获"""
from models.farm_state import ActionType
from core.cv_detector import DetectResult
from core.strategies.base import BaseStrategy


class HarvestStrategy(BaseStrategy):

    def try_harvest(self, detections: list[DetectResult]) -> str | None:
        """检测并点击一键收获按钮"""
        btn = self.find_by_name(detections, "btn_harvest")
        if btn:
            self.click(btn.x, btn.y, "一键收获", ActionType.HARVEST)
            return "一键收获"
        return None
