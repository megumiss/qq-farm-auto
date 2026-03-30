"""策略基类 — 公共方法"""
import time
from loguru import logger

from models.farm_state import Action, ActionType
from core.cv_detector import CVDetector, DetectResult


class BaseStrategy:
    def __init__(self, cv_detector: CVDetector):
        self.cv_detector = cv_detector
        self.action_executor = None
        self._capture_fn = None
        self._stop_requested = False

    def set_capture_fn(self, fn):
        self._capture_fn = fn

    @property
    def stopped(self) -> bool:
        return self._stop_requested

    def capture(self, rect: tuple):
        if self._capture_fn:
            return self._capture_fn(rect, save=False)
        return None, [], None

    def click(self, x: int, y: int, desc: str = "",
              action_type: str = ActionType.NAVIGATE) -> bool:
        if not self.action_executor or self._stop_requested:
            return False
        action = Action(type=action_type, click_position={"x": x, "y": y},
                        priority=0, description=desc)
        result = self.action_executor.execute_action(action)
        if result.success:
            logger.info(f"✓ {desc}")
        else:
            logger.warning(f"✗ {desc}: {result.message}")
        return result.success

    def find_by_name(self, detections: list[DetectResult], name: str) -> DetectResult | None:
        for d in detections:
            if d.name == name:
                return d
        return None

    def find_by_prefix_first(self, detections: list[DetectResult], prefix: str) -> DetectResult | None:
        for d in detections:
            if d.name.startswith(prefix):
                return d
        return None

    def find_any(self, detections: list[DetectResult], names: list[str]) -> DetectResult | None:
        name_set = set(names)
        for d in detections:
            if d.name in name_set:
                return d
        return None

    def click_blank(self, rect: tuple):
        """点击天空区域关闭弹窗"""
        w, h = rect[2], rect[3]
        self.click(w // 2, int(h * 0.15), "点击空白处")
