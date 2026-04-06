"""使用左右边缘模板 + 双方向斜率反推 4x6 地块网格（斜向地块）。

逻辑：
1. 匹配 `btn_land_right` 与 `btn_land_left`（取最佳命中）。
2. 右模板命中的“左边缘中心点”作为右锚点；左模板命中的“右边缘中心点”作为左锚点。
3. 将两个锚点视作整块地网格对角点（起点/终点可配置）。
4. 已知两组方向斜率（列方向 + 行方向），按 rows/cols 反解每步像素步长。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / 'tools' / 'screenshots'


def _imread(path: Path) -> np.ndarray:
    """支持中文路径读取。"""
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f'读取图片失败: {path}')
    return image


def _imwrite(path: Path, image: np.ndarray) -> None:
    """支持中文路径写入。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode('.png', image)
    if not ok:
        raise ValueError(f'写入图片失败: {path}')
    encoded.tofile(str(path))


def _latest_image_in_root() -> Path | None:
    patterns = ('*.png', '*.jpg', '*.jpeg', '*.bmp', '*.webp')
    files: list[Path] = []
    for pat in patterns:
        files.extend(ROOT.glob(pat))
    if not files:
        return None
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def _effective_template(tpl_full: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """从整屏模板提取非黑有效区域。"""
    mask = np.any(tpl_full > 0, axis=2)
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError('模板全黑，无法提取有效区域')
    x1, y1 = int(xs.min()), int(ys.min())
    x2, y2 = int(xs.max() + 1), int(ys.max() + 1)
    crop = tpl_full[y1:y2, x1:x2].copy()
    return crop, (x1, y1, x2, y2)


def _match_best(image: np.ndarray, tpl: np.ndarray) -> tuple[int, int, float]:
    """返回最佳匹配位置与分数。"""
    result = cv2.matchTemplate(image, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    return int(max_loc[0]), int(max_loc[1]), float(max_val)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='左右边缘模板 + 双斜率 -> 地块 4x6 网格反推测试')
    parser.add_argument('--image', type=str, default='', help='输入图片；留空则取根目录最新图片')
    parser.add_argument('--rows', type=int, default=4, help='网格行数，默认4')
    parser.add_argument('--cols', type=int, default=6, help='网格列数，默认6')
    parser.add_argument(
        '--start-anchor',
        type=str,
        default='right',
        choices=['right', 'left'],
        help='网格起点锚点：right 或 left（另一个锚点视作终点）',
    )
    parser.add_argument(
        '--slope-col',
        type=float,
        default=-0.5091743119,
        help='列方向斜率（dy/dx），默认使用你提供的斜率',
    )
    parser.add_argument(
        '--slope-row',
        type=float,
        default=0.5091743119,
        help='行方向斜率（dy/dx），默认假设为另一方向对称斜率',
    )
    parser.add_argument(
        '--left-template', type=str, default='templates/qq/btn/btn_land_left.png', help='左边缘模板路径'
    )
    parser.add_argument(
        '--right-template',
        type=str,
        default='templates/qq/btn/btn_land_right.png',
        help='右边缘模板路径',
    )
    parser.add_argument('--out-dir', type=str, default=str(DEFAULT_OUT_DIR), help='输出目录')
    parser.add_argument('--show', action='store_true', help='是否弹窗显示结果')
    return parser.parse_args()


def _unit_by_slope(slope: float) -> np.ndarray:
    vec = np.array([1.0, float(slope)], dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-6:
        return np.array([1.0, 0.0], dtype=np.float32)
    return vec / norm


def _grid_points_by_slopes(
    start_anchor: tuple[float, float],
    end_anchor: tuple[float, float],
    step_rows: int,
    step_cols: int,
    slope_col: float,
    slope_row: float,
) -> tuple[list[list[tuple[float, float]]], np.ndarray, np.ndarray, float, float]:
    """根据对角锚点 + 双方向斜率，反解行列步长并生成网格点。"""
    step_rows = max(0, int(step_rows))
    step_cols = max(0, int(step_cols))
    if step_rows == 0 and step_cols == 0:
        return [[(float(start_anchor[0]), float(start_anchor[1]))]], np.zeros(2), np.zeros(2), 0.0, 0.0

    start = np.array([float(start_anchor[0]), float(start_anchor[1])], dtype=np.float32)
    end = np.array([float(end_anchor[0]), float(end_anchor[1])], dtype=np.float32)
    delta = end - start
    u = _unit_by_slope(float(slope_col))
    v = _unit_by_slope(float(slope_row))

    nx = float(step_cols)
    ny = float(step_rows)
    mat = np.column_stack((u * nx, v * ny)).astype(np.float32)
    det = float(np.linalg.det(mat))
    if abs(det) < 1e-6:
        raise ValueError('双方向斜率线性相关，无法反解步长，请调整 slope-row 或 slope-col')

    scale_col, scale_row = np.linalg.solve(mat, delta)
    col_step = u * float(scale_col)
    row_step = v * float(scale_row)

    grid: list[list[tuple[float, float]]] = []
    for r in range(step_rows + 1):
        row_points: list[tuple[float, float]] = []
        for c in range(step_cols + 1):
            p = start + col_step * float(c) + row_step * float(r)
            row_points.append((float(p[0]), float(p[1])))
        grid.append(row_points)
    return grid, col_step, row_step, float(scale_col), float(scale_row)


def main() -> None:
    args = _parse_args()
    image_path = Path(args.image) if args.image else _latest_image_in_root()
    if image_path is None or not image_path.exists():
        raise SystemExit('未找到输入图片，请通过 --image 指定')

    image = _imread(image_path)

    left_tpl_full = _imread(ROOT / args.left_template)
    right_tpl_full = _imread(ROOT / args.right_template)
    left_tpl, _ = _effective_template(left_tpl_full)
    right_tpl, _ = _effective_template(right_tpl_full)

    lx, ly, lscore = _match_best(image, left_tpl)
    rx, ry, rscore = _match_best(image, right_tpl)
    lh, lw = left_tpl.shape[:2]
    rh, rw = right_tpl.shape[:2]

    # 按你的逻辑：
    # - 右模板：匹配框左边缘中心
    # - 左模板：匹配框右边缘中心
    right_anchor = (float(rx), float(ry + rh / 2.0))
    left_anchor = (float(lx + lw), float(ly + lh / 2.0))

    start_anchor = right_anchor if args.start_anchor == 'right' else left_anchor
    end_anchor = left_anchor if args.start_anchor == 'right' else right_anchor
    # 这里按“4x6 表格角点”求解：列步数=cols，行步数=rows
    corner_grid, col_step, row_step, scale_col, scale_row = _grid_points_by_slopes(
        start_anchor=start_anchor,
        end_anchor=end_anchor,
        step_rows=int(args.rows),
        step_cols=int(args.cols),
        slope_col=float(args.slope_col),
        slope_row=float(args.slope_row),
    )

    # 由角点表格反推出每个地块中心（rows x cols）
    centers: list[list[tuple[float, float]]] = []
    for r in range(int(args.rows)):
        row_centers: list[tuple[float, float]] = []
        for c in range(int(args.cols)):
            p00 = np.array(corner_grid[r][c], dtype=np.float32)
            p11 = np.array(corner_grid[r + 1][c + 1], dtype=np.float32)
            center = (p00 + p11) * 0.5
            row_centers.append((float(center[0]), float(center[1])))
        centers.append(row_centers)

    out = image.copy()
    # 绘制模板命中框
    cv2.rectangle(out, (lx, ly), (lx + lw, ly + lh), (255, 120, 0), 1, cv2.LINE_AA)
    cv2.rectangle(out, (rx, ry), (rx + rw, ry + rh), (0, 180, 255), 1, cv2.LINE_AA)
    cv2.circle(out, (int(round(left_anchor[0])), int(round(left_anchor[1]))), 5, (255, 120, 0), -1, cv2.LINE_AA)
    cv2.circle(out, (int(round(right_anchor[0])), int(round(right_anchor[1]))), 5, (0, 180, 255), -1, cv2.LINE_AA)

    # 绘制 4x6 表格（每个地块一个四边形）
    for r in range(int(args.rows)):
        for c in range(int(args.cols)):
            p1 = corner_grid[r][c]
            p2 = corner_grid[r][c + 1]
            p3 = corner_grid[r + 1][c + 1]
            p4 = corner_grid[r + 1][c]
            poly = np.array(
                [
                    [int(round(p1[0])), int(round(p1[1]))],
                    [int(round(p2[0])), int(round(p2[1]))],
                    [int(round(p3[0])), int(round(p3[1]))],
                    [int(round(p4[0])), int(round(p4[1]))],
                ],
                dtype=np.int32,
            )
            cv2.polylines(out, [poly], True, (80, 180, 80), 1, cv2.LINE_AA)
            center = centers[r][c]
            logical_row = int(args.rows) - r
            label = f'{c + 1}-{logical_row}'
            cv2.putText(
                out,
                label,
                (int(round(center[0])) + 4, int(round(center[1])) - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (60, 230, 60),
                1,
                cv2.LINE_AA,
            )

    out_dir = Path(args.out_dir)
    stem = image_path.stem
    img_out = out_dir / f'{stem}_land_grid_by_edges.png'
    json_out = out_dir / f'{stem}_land_grid_by_edges.json'
    _imwrite(img_out, out)

    payload = {
        'image': str(image_path),
        'rows': int(args.rows),
        'cols': int(args.cols),
        'start_anchor': args.start_anchor,
        'slope_col': float(args.slope_col),
        'slope_row': float(args.slope_row),
        'left_template': args.left_template,
        'right_template': args.right_template,
        'left_match': {'x': lx, 'y': ly, 'w': lw, 'h': lh, 'score': round(lscore, 6)},
        'right_match': {'x': rx, 'y': ry, 'w': rw, 'h': rh, 'score': round(rscore, 6)},
        'left_anchor': [round(left_anchor[0], 3), round(left_anchor[1], 3)],
        'right_anchor': [round(right_anchor[0], 3), round(right_anchor[1], 3)],
        'start_point': [round(start_anchor[0], 3), round(start_anchor[1], 3)],
        'end_point': [round(end_anchor[0], 3), round(end_anchor[1], 3)],
        'col_step': [round(float(col_step[0]), 6), round(float(col_step[1]), 6)],
        'row_step': [round(float(row_step[0]), 6), round(float(row_step[1]), 6)],
        'scale_col': round(scale_col, 6),
        'scale_row': round(scale_row, 6),
        'cell_rows': int(args.rows),
        'cell_cols': int(args.cols),
        'cell_count': int(args.rows) * int(args.cols),
        'corner_grid': [
            [{'row': r + 1, 'col': c + 1, 'x': round(p[0], 3), 'y': round(p[1], 3)} for c, p in enumerate(row)]
            for r, row in enumerate(corner_grid)
        ],
        'grid': [
            [
                {
                    'row': int(args.rows) - r,
                    'col': c + 1,
                    'label': f'{c + 1}-{int(args.rows) - r}',
                    'x': round(p[0], 3),
                    'y': round(p[1], 3),
                }
                for c, p in enumerate(row)
            ]
            for r, row in enumerate(centers)
        ],
        'output_image': str(img_out.resolve()),
    }
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'输入图片: {image_path}')
    print(f'左模板匹配分数: {lscore:.4f} | 右模板匹配分数: {rscore:.4f}')
    print(f'左锚点: ({left_anchor[0]:.2f}, {left_anchor[1]:.2f})')
    print(f'右锚点: ({right_anchor[0]:.2f}, {right_anchor[1]:.2f})')
    print(f'起点: ({start_anchor[0]:.2f}, {start_anchor[1]:.2f}) -> 终点: ({end_anchor[0]:.2f}, {end_anchor[1]:.2f})')
    print(f'列方向斜率: {float(args.slope_col):.6f} | 行方向斜率: {float(args.slope_row):.6f}')
    print(f'列步长: ({col_step[0]:.3f}, {col_step[1]:.3f}) | 行步长: ({row_step[0]:.3f}, {row_step[1]:.3f})')
    print(f'列尺度: {scale_col:.3f} | 行尺度: {scale_row:.3f}')
    print(f'输出图: {img_out.resolve()}')
    print(f'输出JSON: {json_out.resolve()}')

    if args.show:
        cv2.imshow('land_grid_by_edges', out)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
