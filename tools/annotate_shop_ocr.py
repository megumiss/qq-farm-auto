"""OCR annotate shop item info directly on full screenshots.

Output:
- Annotated images under screenshots/shop_ocr_annotated/
- Parsed table under screenshots/shop_ocr_annotated/manifest.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import argparse
import csv
import re
import sys

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.ocr_utils import OCRItem, OCRTool


DEFAULT_SCREENSHOT_GLOB = "PixPin_2026-03-31_19-50-*.png"
OUT_DIR = ROOT / "screenshots" / "shop_ocr_annotated"
OUT_CSV = OUT_DIR / "manifest.csv"


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int
    area: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Annotate shop item info with OCR.")
    parser.add_argument("--glob", default=DEFAULT_SCREENSHOT_GLOB, help="Screenshot glob under project root.")
    parser.add_argument("--clean", action="store_true", help="Clear previous outputs before run.")
    return parser.parse_args()


def read_like_template_collector(path: Path) -> np.ndarray:
    pil = Image.open(path).convert("RGB")
    rgb = np.array(pil)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def iou(a: Rect, b: Rect) -> float:
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def detect_shop_cards(img_bgr: np.ndarray) -> list[Rect]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edge = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edge, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    candidates: list[Rect] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if h == 0:
            continue
        ar = w / h
        if 25000 <= area <= 42000 and 0.90 <= ar <= 1.05:
            candidates.append(Rect(x, y, w, h, area))

    candidates.sort(key=lambda r: r.area, reverse=True)
    kept: list[Rect] = []
    for r in candidates:
        if all(iou(r, k) < 0.35 for k in kept):
            kept.append(r)

    kept.sort(key=lambda r: (r.y, r.x))
    return kept


def row_col_indices(rects: list[Rect]) -> list[tuple[int, int]]:
    if not rects:
        return []
    rows: list[list[Rect]] = []
    y_tol = 25
    for r in rects:
        placed = False
        for row in rows:
            if abs(r.y - row[0].y) <= y_tol:
                row.append(r)
                placed = True
                break
        if not placed:
            rows.append([r])
    for row in rows:
        row.sort(key=lambda t: t.x)

    pos_map: dict[tuple[int, int, int, int], tuple[int, int]] = {}
    for ri, row in enumerate(rows, start=1):
        for ci, r in enumerate(row, start=1):
            pos_map[(r.x, r.y, r.w, r.h)] = (ri, ci)
    return [pos_map[(r.x, r.y, r.w, r.h)] for r in rects]


def clean_text(s: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9（）()]+", "", s).strip()


def collect_vocab() -> list[str]:
    vocab: set[str] = set()
    for p in (ROOT / "templates").glob("seed_*.png"):
        vocab.add(p.stem[len("seed_"):])
    for p in (ROOT / "templates").glob("shop_*.png"):
        if "shop_extracted_auto" in str(p):
            continue
        vocab.add(p.stem[len("shop_"):])
    return sorted(vocab)


def resolve_name(raw: str, vocab: list[str]) -> str:
    text = clean_text(raw)
    if not text:
        return ""
    if text in vocab:
        return text

    starts = [v for v in vocab if v.startswith(text)]
    if len(starts) == 1:
        return starts[0]

    best_name = text
    best_score = 0.0
    for v in vocab:
        score = SequenceMatcher(None, text, v).ratio()
        if score > best_score:
            best_score = score
            best_name = v
    return best_name if best_score >= 0.70 else text


def point_in_rect(x: float, y: float, r: Rect) -> bool:
    return r.x <= x <= r.x2 and r.y <= y <= r.y2


def pick_card_texts(items: list[OCRItem], rect: Rect) -> list[OCRItem]:
    out: list[OCRItem] = []
    for it in items:
        xs = [p[0] for p in it.box]
        ys = [p[1] for p in it.box]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        if point_in_rect(cx, cy, rect):
            out.append(it)
    return out


def parse_item_info(card_items: list[OCRItem], vocab: list[str]) -> tuple[str, str, str]:
    grade = ""
    name = ""
    price = ""

    names: list[tuple[str, float]] = []
    prices: list[tuple[str, float]] = []
    grades: list[tuple[str, float]] = []

    for it in card_items:
        t = clean_text(it.text)
        if not t:
            continue
        if re.match(r"^\d+品$", t):
            grades.append((t, it.score))
            continue
        if re.match(r"^\d+$", t):
            prices.append((t, it.score))
            continue
        if re.search(r"[\u4e00-\u9fff]", t):
            names.append((resolve_name(t, vocab), it.score))

    if grades:
        grade = sorted(grades, key=lambda x: x[1], reverse=True)[0][0]
    if names:
        name = sorted(names, key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]
    if prices:
        # price is usually the largest pure number in each card
        price = sorted(prices, key=lambda x: int(x[0]), reverse=True)[0][0]

    return grade, name, price


def annotate_image(img: np.ndarray, rects: list[Rect], parsed: list[tuple[str, str, str]]) -> np.ndarray:
    vis = img.copy()
    for i, (r, info) in enumerate(zip(rects, parsed), start=1):
        grade, name, price = info
        cv2.rectangle(vis, (r.x, r.y), (r.x2, r.y2), (0, 0, 255), 2)
        label = f"{i:02d} {grade} {name} {price}".strip()
        cv2.putText(
            vis,
            label,
            (r.x + 2, max(14, r.y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 0, 255),
            1,
        )
    return vis


def main() -> None:
    args = parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.clean:
        for p in OUT_DIR.glob("*"):
            if p.is_file():
                p.unlink(missing_ok=True)

    screenshots = sorted(ROOT.glob(args.glob))
    if not screenshots:
        raise SystemExit(f"No screenshots found: {args.glob}")

    ocr = OCRTool()
    vocab = collect_vocab()
    rows: list[dict[str, str | int]] = []

    for shot in screenshots:
        img = read_like_template_collector(shot)
        rects = detect_shop_cards(img)
        rc = row_col_indices(rects)

        # OCR on whole screenshot; no per-card cropping for OCR.
        all_items = ocr.detect(img, scale=1.4, alpha=1.15, beta=0.0)
        parsed_infos: list[tuple[str, str, str]] = []

        for idx, (rect, (ri, ci)) in enumerate(zip(rects, rc), start=1):
            card_items = pick_card_texts(all_items, rect)
            grade, name, price = parse_item_info(card_items, vocab)
            parsed_infos.append((grade, name, price))
            rows.append(
                {
                    "source_screenshot": shot.name,
                    "index": idx,
                    "row": ri,
                    "col": ci,
                    "grade": grade,
                    "name": name,
                    "price": price,
                    "bbox_x": rect.x,
                    "bbox_y": rect.y,
                    "bbox_w": rect.w,
                    "bbox_h": rect.h,
                    "ocr_items_in_card": len(card_items),
                }
            )

        vis = annotate_image(img, rects, parsed_infos)
        out_img = OUT_DIR / f"{shot.stem}_ocr_annotated.png"
        ok, buf = cv2.imencode(".png", vis)
        if ok:
            out_img.write_bytes(buf.tobytes())

        print(f"{shot.name}: cards={len(rects)} parsed={len(parsed_infos)} out={out_img.name}")

    if rows:
        with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print(f"done: screenshots={len(screenshots)}")
    print(f"annotated_dir={OUT_DIR}")
    print(f"manifest={OUT_CSV}")


if __name__ == "__main__":
    main()
