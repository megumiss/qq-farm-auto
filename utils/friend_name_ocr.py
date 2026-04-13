"""好友昵称 OCR 识别。"""

from __future__ import annotations

import numpy as np

from utils.ocr_utils import OCRTool


class FriendNameOCR:
    """封装好友昵称识别，复用全局 OCR 实例。"""

    _shared_ocr: OCRTool | None = None

    def __init__(self):
        """初始化并复用 OCR 实例。"""
        if FriendNameOCR._shared_ocr is None:
            FriendNameOCR._shared_ocr = OCRTool()
        self.ocr = FriendNameOCR._shared_ocr

    def detect_name(
        self,
        img_bgr: np.ndarray,
        *,
        region: tuple[int, int, int, int] | None = None,
    ) -> tuple[str, float]:
        """识别好友昵称并返回 `(name, score)`。"""
        if img_bgr is None:
            return '', 0.0
        text, score = self.ocr.detect_text(
            img_bgr,
            region=region,
            scale=1.4,
            alpha=1.15,
            beta=0.0,
            joiner='',
        )
        return str(text or '').strip(), float(score or 0.0)
