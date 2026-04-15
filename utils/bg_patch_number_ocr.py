"""固定底色数字块 OCR 识别工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from utils.ocr_provider import get_ocr_tool
from utils.ocr_utils import OCRTool


@dataclass
class BgPatchNumberItem:
    """单个数字识别结果。"""

    text: str
    raw_text: str
    score: float
    box: tuple[int, int, int, int]  # (x, y, w, h), 基于全图坐标


class BgPatchNumberOCR:
    """基于固定底色块提取数字（支持传入全图与可选裁剪范围）。"""

    _NUM_PATTERN = re.compile(r'\d+')

    def __init__(
        self,
        ocr_tool: OCRTool | None = None,
        *,
        scope: str = 'engine',
        key: str | None = None,
        target_rgb: tuple[int, int, int] = (244, 231, 204),
        tolerance: int = 12,
        min_width: int = 28,
        max_width: int = 46,
        min_height: int = 18,
        max_height: int = 26,
        min_area: int = 500,
        max_area: int = 1200,
        patch_pad: int = 3,
        upsample_scale: float = 4.0,
    ):
        """初始化识别器参数。"""
        self.ocr = ocr_tool or get_ocr_tool(scope=scope, key=key)
        self.target_bgr = np.array(
            [int(target_rgb[2]), int(target_rgb[1]), int(target_rgb[0])],
            dtype=np.int16,
        )
        self.tolerance = int(tolerance)
        self.min_width = int(min_width)
        self.max_width = int(max_width)
        self.min_height = int(min_height)
        self.max_height = int(max_height)
        self.min_area = int(min_area)
        self.max_area = int(max_area)
        self.patch_pad = int(patch_pad)
        self.upsample_scale = float(upsample_scale)

    @staticmethod
    def _clip_region(region: tuple[int, int, int, int], w: int, h: int) -> tuple[int, int, int, int]:
        x1, y1, x2, y2 = region
        x1 = max(0, min(int(x1), w - 1))
        y1 = max(0, min(int(y1), h - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y2 = max(y1 + 1, min(int(y2), h))
        return x1, y1, x2, y2

    def _build_mask(self, img_bgr: np.ndarray) -> np.ndarray:
        diff = np.abs(img_bgr.astype(np.int16) - self.target_bgr[None, None, :])
        mask = (
            (diff[:, :, 0] <= self.tolerance) & (diff[:, :, 1] <= self.tolerance) & (diff[:, :, 2] <= self.tolerance)
        ).astype(np.uint8) * 255
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            np.ones((3, 3), np.uint8),
            iterations=1,
        )
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), np.uint8),
            iterations=1,
        )
        return mask

    def _find_candidate_boxes(self, mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: list[tuple[int, int, int, int]] = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if not (self.min_width <= w <= self.max_width):
                continue
            if not (self.min_height <= h <= self.max_height):
                continue
            if not (self.min_area <= area <= self.max_area):
                continue
            boxes.append((x, y, w, h))
        boxes.sort(key=lambda item: (item[1], item[0]))
        return boxes

    def _recognize_patch(self, patch_bgr: np.ndarray) -> tuple[str, str, float]:
        if patch_bgr is None or patch_bgr.size == 0:
            return '', '', 0.0

        up = cv2.resize(
            patch_bgr,
            None,
            fx=self.upsample_scale,
            fy=self.upsample_scale,
            interpolation=cv2.INTER_CUBIC if self.upsample_scale > 1 else cv2.INTER_AREA,
        )
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        rec_input = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

        # 使用 RapidOCR 的 rec-only 路径，避免检测阶段干扰小块数字。
        # 注意：RapidOCR 会持久化 use_det/use_cls/use_rec/text_score 等状态，这里做调用后恢复。
        rapid_ocr = self.ocr._ocr
        prev_use_det = getattr(rapid_ocr, 'use_det', True)
        prev_use_cls = getattr(rapid_ocr, 'use_cls', True)
        prev_use_rec = getattr(rapid_ocr, 'use_rec', True)
        prev_text_score = getattr(rapid_ocr, 'text_score', 0.5)
        try:
            res = rapid_ocr(
                rec_input,
                use_det=False,
                use_cls=False,
                use_rec=True,
                text_score=0.0,
            )
        finally:
            try:
                rapid_ocr.update_params(
                    use_det=bool(prev_use_det),
                    use_cls=bool(prev_use_cls),
                    use_rec=bool(prev_use_rec),
                    text_score=float(prev_text_score),
                )
            except Exception:
                # 仅兜底，不影响本次识别结果。
                pass
        txts = list(getattr(res, 'txts', []) or [])
        scores = list(getattr(res, 'scores', []) or [])
        raw = str(txts[0]).strip() if txts else ''
        score = float(scores[0]) if scores else 0.0

        matched = self._NUM_PATTERN.findall(raw)
        text = matched[0] if matched else ''
        return text, raw, score

    def detect_items(
        self,
        img_bgr: np.ndarray,
        *,
        region: tuple[int, int, int, int] | None = None,
    ) -> list[BgPatchNumberItem]:
        """识别数字并返回结构化结果（`box` 为全图坐标）。"""
        if img_bgr is None or img_bgr.size == 0:
            return []

        h, w = img_bgr.shape[:2]
        if region is None:
            x1, y1, x2, y2 = 0, 0, w, h
        else:
            x1, y1, x2, y2 = self._clip_region(region, w, h)

        work = img_bgr[y1:y2, x1:x2]
        mask = self._build_mask(work)
        boxes = self._find_candidate_boxes(mask)

        out: list[BgPatchNumberItem] = []
        for bx, by, bw, bh in boxes:
            px1 = max(0, bx - self.patch_pad)
            py1 = max(0, by - self.patch_pad)
            px2 = min(work.shape[1], bx + bw + self.patch_pad)
            py2 = min(work.shape[0], by + bh + self.patch_pad)
            patch = work[py1:py2, px1:px2]

            text, raw, score = self._recognize_patch(patch)
            if not text:
                continue

            out.append(
                BgPatchNumberItem(
                    text=text,
                    raw_text=raw,
                    score=score,
                    box=(bx + x1, by + y1, bw, bh),
                )
            )
        return out

    def detect_numbers(
        self,
        img_bgr: np.ndarray,
        *,
        region: tuple[int, int, int, int] | None = None,
    ) -> list[str]:
        """返回识别出的数字文本列表。"""
        return [item.text for item in self.detect_items(img_bgr, region=region)]

    @staticmethod
    def draw_results(img_bgr: np.ndarray, items: list[BgPatchNumberItem]) -> np.ndarray:
        """在图像上绘制识别框和数字。"""
        output = img_bgr.copy()
        for idx, item in enumerate(items, start=1):
            x, y, w, h = item.box
            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 255), 2)
            label_y = y - 6 if y > 10 else y + h + 16
            label = f'{idx}:{item.text}({item.score:.3f})'
            cv2.putText(
                output,
                label,
                (x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.60,
                (0, 220, 255),
                2,
                cv2.LINE_AA,
            )
        return output
