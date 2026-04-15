"""OCR utility based on RapidOCR."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from rapidocr import EngineType, LangDet, LangRec, ModelType

try:
    from rapidocr import OCRVersion, RapidOCR
except ImportError as exc:  # pragma: no cover
    raise RuntimeError('Missing dependency `rapidocr`. Please install requirements first.') from exc


@dataclass
class OCRItem:
    """Single OCR result item."""

    box: list[list[float]]
    text: str
    score: float


class OCRTool:
    """Reusable OCR helper.

    Supports input types:
    - str / Path: image file path
    - PIL.Image.Image
    - np.ndarray (BGR/BGRA/RGB/GRAY)
    """

    def __init__(self):
        """初始化对象并准备运行所需状态。"""
        self._ocr = RapidOCR(
            params={
                'Det.engine_type': EngineType.ONNXRUNTIME,
                'Det.lang_type': LangDet.CH,
                'Det.model_type': ModelType.MOBILE,
                'Det.ocr_version': OCRVersion.PPOCRV5,
                'Rec.engine_type': EngineType.ONNXRUNTIME,
                'Rec.lang_type': LangRec.CH,
                'Rec.model_type': ModelType.MOBILE,
                'Rec.ocr_version': OCRVersion.PPOCRV5,
            }
        )

    @staticmethod
    def _to_raw_items(ocr_result: Any) -> list[tuple[list[list[float]], str, float]]:
        """将 RapidOCR 结果转换为统一结构。"""
        boxes = getattr(ocr_result, 'boxes', None)
        txts = getattr(ocr_result, 'txts', None)
        scores = getattr(ocr_result, 'scores', None)
        if boxes is None or txts is None or scores is None:
            return []

        out: list[tuple[list[list[float]], str, float]] = []
        for box, text, score in zip(boxes, txts, scores):
            points = [[float(pt[0]), float(pt[1])] for pt in box]
            out.append((points, str(text), float(score)))
        return out

    @staticmethod
    def _to_bgr(image: str | Path | Image.Image | np.ndarray) -> np.ndarray:
        """将 `bgr` 转换为目标格式。"""
        if isinstance(image, (str, Path)):
            path = Path(image)
            arr = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if arr is None:
                raise ValueError(f'Failed to read image: {path}')
            image = arr

        if isinstance(image, Image.Image):
            rgb = np.array(image.convert('RGB'))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        if not isinstance(image, np.ndarray):
            raise TypeError(f'Unsupported image type: {type(image)}')

        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.ndim != 3:
            raise ValueError(f'Invalid ndarray image shape: {image.shape}')

        # BGRA -> BGR
        if image.shape[2] == 4:
            return image[:, :, :3]
        # BGR/RGB are both 3-channel; caller controls color semantics.
        if image.shape[2] == 3:
            return image
        raise ValueError(f'Unsupported channel count: {image.shape[2]}')

    @staticmethod
    def _clip_region(region: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
        """执行 `clip region` 相关处理。"""
        x1, y1, x2, y2 = region
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        if x2 <= x1 or y2 <= y1:
            raise ValueError(f'Invalid region after clipping: {(x1, y1, x2, y2)}')
        return x1, y1, x2, y2

    def detect(
        self,
        image: str | Path | Image.Image | np.ndarray,
        region: tuple[int, int, int, int] | None = None,
        scale: float = 1.0,
        alpha: float = 1.0,
        beta: float = 0.0,
    ) -> list[OCRItem]:
        """Run OCR and return structured items.

        Args:
            image: input image.
            region: optional ROI (x1, y1, x2, y2) in original coordinates.
            scale: resize factor before OCR.
            alpha/beta: cv2.convertScaleAbs params for contrast adjustment.
        """
        bgr = self._to_bgr(image)
        h, w = bgr.shape[:2]
        offset_x = 0
        offset_y = 0

        if region is not None:
            x1, y1, x2, y2 = self._clip_region(region, w, h)
            bgr = bgr[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1

        if scale != 1.0:
            bgr = cv2.resize(
                bgr,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA,
            )

        if alpha != 1.0 or beta != 0.0:
            bgr = cv2.convertScaleAbs(bgr, alpha=alpha, beta=beta)

        # 强制启用 det/cls/rec，避免其他调用（例如 rec-only）污染共享 OCR 实例状态。
        raw_items = self._to_raw_items(self._ocr(bgr, use_det=True, use_cls=True, use_rec=True))
        if not raw_items:
            return []

        items: list[OCRItem] = []
        inv = 1.0 / scale if scale != 0 else 1.0
        for box, text, score in raw_items:
            mapped_box: list[list[float]] = []
            for pt in box:
                px = float(pt[0]) * inv + offset_x
                py = float(pt[1]) * inv + offset_y
                mapped_box.append([px, py])
            items.append(OCRItem(box=mapped_box, text=str(text), score=float(score)))
        return items

    def detect_text(
        self,
        image: str | Path | Image.Image | np.ndarray,
        region: tuple[int, int, int, int] | None = None,
        scale: float = 1.0,
        alpha: float = 1.0,
        beta: float = 0.0,
        joiner: str = '',
    ) -> tuple[str, float]:
        """Run OCR and return merged text and average confidence."""
        items = self.detect(image, region=region, scale=scale, alpha=alpha, beta=beta)
        if not items:
            return '', 0.0

        # Keep reading order by left-most x of each box.
        ordered = sorted(items, key=lambda it: min(pt[0] for pt in it.box))
        text = joiner.join(it.text for it in ordered)
        score = float(sum(it.score for it in ordered) / len(ordered))
        return text, score

    @staticmethod
    def to_dict(items: list[OCRItem]) -> list[dict[str, Any]]:
        """Convert OCR items to plain dict list for logging/serialization."""
        return [{'box': it.box, 'text': it.text, 'score': it.score} for it in items]
