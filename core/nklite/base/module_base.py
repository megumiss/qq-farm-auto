"""精简版 NIKKE ModuleBase。"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from core.cv_detector import CVDetector
from core.nklite.base.button import Button
from core.nklite.base.timer import Timer


class ModuleBase:
    def __init__(self, config: Any, detector: CVDetector, device):
        self.config = config
        self.cv_detector = detector
        self.device = device
        self.interval_timer: dict[str, Timer] = {}
        Button.set_match_provider(self._match_button)

    @staticmethod
    def _norm_offset(offset: int | tuple[int, int] | tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        if isinstance(offset, tuple):
            if len(offset) == 2:
                return -int(offset[0]), -int(offset[1]), int(offset[0]), int(offset[1])
            if len(offset) == 4:
                return int(offset[0]), int(offset[1]), int(offset[2]), int(offset[3])
        value = int(offset)
        return -3, -value, 3, value

    def _match_button(
        self,
        button: Button,
        image: np.ndarray,
        offset: int | tuple[int, int] | tuple[int, int, int, int],
        threshold: float,
        static: bool,
    ) -> tuple[bool, tuple[int, int, int, int] | None, float]:
        if image is None:
            return False, None, 0.0
        button.ensure_template()
        if button.image is None:
            return False, None, 0.0

        search_img = image
        off = (0, 0, 0, 0)
        if static:
            off = self._norm_offset(offset)
            search_area = (
                int(button.area[0] + off[0]),
                int(button.area[1] + off[1]),
                int(button.area[2] + off[2]),
                int(button.area[3] + off[3]),
            )
            search_img = self._crop_like_pillow(image, search_area)

        # 对齐 NIKKE Button.match：直接模板匹配，不走 detector 多尺度分支。
        result = cv2.matchTemplate(button.image, search_img, cv2.TM_CCOEFF_NORMED)
        _, similarity, _, upper_left = cv2.minMaxLoc(result)
        hit = float(similarity) > float(threshold)
        if not hit:
            return False, None, float(similarity)

        if static:
            dx = int(off[0] + upper_left[0])
            dy = int(off[1] + upper_left[1])
            area = (
                int(button._button[0] + dx),
                int(button._button[1] + dy),
                int(button._button[2] + dx),
                int(button._button[3] + dy),
            )
            return True, area, float(similarity)

        h = int(button.area[3] - button.area[1])
        w = int(button.area[2] - button.area[0])
        area = (
            int(upper_left[0]),
            int(upper_left[1]),
            int(upper_left[0] + w),
            int(upper_left[1] + h),
        )
        return True, area, float(similarity)

    @staticmethod
    def _crop_like_pillow(image: np.ndarray, area: tuple[int, int, int, int]) -> np.ndarray:
        x1, y1, x2, y2 = [int(round(v)) for v in area]
        h, w = image.shape[:2]

        top = max(0, 0 - y1)
        bottom = max(0, y2 - h)
        left = max(0, 0 - x1)
        right = max(0, x2 - w)

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = max(0, x2)
        y2 = max(0, y2)

        cropped = image[y1:y2, x1:x2].copy()
        if top or bottom or left or right:
            cropped = cv2.copyMakeBorder(
                cropped,
                top,
                bottom,
                left,
                right,
                borderType=cv2.BORDER_CONSTANT,
                value=(0, 0, 0),
            )
        return cropped

    def appear_any(self, buttons, **kwargs):
        for btn in buttons:
            if self.appear(btn, **kwargs):
                return True
        return False

    def appear_then_click_any(self, buttons, **kwargs):
        for btn in buttons:
            if self.appear_then_click(btn, **kwargs):
                return True
        return False

    def _button_interval_ready(self, key: str, interval: float) -> bool:
        if interval <= 0:
            return True
        timer = self.interval_timer.get(key)
        if timer is None or abs(timer.limit - float(interval)) > 1e-6:
            timer = Timer(interval)
            self.interval_timer[key] = timer
        return timer.reached()

    def _button_interval_hit(self, key: str):
        timer = self.interval_timer.get(key)
        if timer:
            timer.reset()

    def appear(self, button: Button, offset=0, interval=0, threshold=None, static=True) -> bool:
        image = self.device.image
        if image is None:
            return False

        key = button.name
        if interval and not self._button_interval_ready(key, float(interval)):
            return False

        if offset:
            t = float(threshold) if threshold is not None else 0.8
            hit = button.match(image, offset=offset, threshold=t, static=static)
        else:
            t = float(threshold) if threshold is not None else 20.0
            hit = button.appear_on(image, threshold=t)

        if hit and interval:
            self._button_interval_hit(key)
        return bool(hit)

    def appear_then_click(
        self, button: Button, offset=0, click_offset=0, interval=0, threshold=None, static=True, screenshot=False
    ) -> bool:
        # 对无模板按钮（如点击空白处）直接点击，保持 NIKKE 式导航可用。
        if not button.file:
            return bool(self.device.click(button, click_offset))

        hit = self.appear(button=button, offset=offset, interval=interval, threshold=threshold, static=static)
        if not hit:
            return False
        if screenshot:
            self.device.screenshot()
        return bool(self.device.click(button, click_offset))

    def interval_reset(self, button):
        if isinstance(button, (list, tuple)):
            for b in button:
                self.interval_reset(b)
            return
        key = button.name if hasattr(button, 'name') else str(button)
        timer = self.interval_timer.get(key)
        if timer:
            timer.reset()
