"""地块巡查任务。"""

from __future__ import annotations

import re

from loguru import logger

from core.engine.task.registry import TaskResult
from core.ui.assets import (
    BTN_CROP_MATURITY_TIME_SUFFIX,
    BTN_CROP_REMOVAL,
    BTN_EXPAND_BRAND,
    BTN_LAND_LEFT,
    BTN_LAND_POP_EMPTY,
    BTN_LAND_RIGHT,
)
from core.ui.page import GOTO_MAIN, page_main
from tasks.base import TaskBase
from utils.land_grid import LandCell, get_lands_from_land_anchor
from utils.ocr_utils import OCRItem, OCRTool

# 画面横向回正手势点位 P1。
LAND_SCAN_SWIPE_H_P1 = (350, 190)
# 画面横向回正手势点位 P2。
LAND_SCAN_SWIPE_H_P2 = (200, 190)
# 地块网格行数（逻辑行）。
LAND_SCAN_ROWS = 4
# 地块网格列数（逻辑列）。
LAND_SCAN_COLS = 6
# 固定截图宽高（宽x高）。
LAND_SCAN_FRAME_WIDTH = 540
LAND_SCAN_FRAME_HEIGHT = 960
# 画面物理列总数（1,2,3,4,4,4,3,2,1）。
LAND_SCAN_PHYSICAL_COLS = 9
# 左滑阶段按“右到左”扫描的物理列数量。
LAND_SCAN_LEFT_STAGE_COL_COUNT = 5
# 右滑阶段按“左到右”扫描的物理列数量。
LAND_SCAN_RIGHT_STAGE_COL_COUNT = 4
# 成熟时间 OCR 识别大区域：相对 BTN_CROP_MATURITY_TIME_SUFFIX 中心 (dx1, dy1, dx2, dy2)。
LAND_SCAN_OCR_REGION_OFFSET = (-200, -50, 100, 50)
# 成熟时间 OCR 二次筛选窗口：相对 BTN_CROP_MATURITY_TIME_SUFFIX 中心，x 起点偏移（像素）。
LAND_SCAN_TIME_PICK_X1 = -100
# 成熟时间 OCR 二次筛选窗口：相对 BTN_CROP_MATURITY_TIME_SUFFIX 中心，x 终点偏移（像素）。
LAND_SCAN_TIME_PICK_X2 = -40
# 成熟时间 OCR 二次筛选窗口：相对 BTN_CROP_MATURITY_TIME_SUFFIX 中心，y 上边界偏移（像素）。
LAND_SCAN_TIME_PICK_Y1 = -20
# 成熟时间 OCR 二次筛选窗口：相对 BTN_CROP_MATURITY_TIME_SUFFIX 中心，y 下边界偏移（像素）。
LAND_SCAN_TIME_PICK_Y2 = 20
# 成熟时间文本正则（仅提取 HH:MM:SS）。
LAND_SCAN_MATURITY_TIME_PATTERN = re.compile(r'(\d{2}:\d{2}:\d{2})')
# 地块等级文本正则（中文等级关键词）。
LAND_SCAN_LEVEL_PATTERN = re.compile(r'(未扩建|普通|红|黑|金)')
# 空地弹窗地块等级 OCR 区域：相对 BTN_LAND_POP_EMPTY 中心 (dx1, dy1, dx2, dy2)。
LAND_SCAN_LEVEL_REGION_OFFSET = (-60, -50, 40, 50)


class TaskLandScan(TaskBase):
    """按预设顺序遍历地块并进行 OCR 收集。"""

    def __init__(self, engine, ui, *, ocr_tool: OCRTool | None = None):
        super().__init__(engine, ui)
        self.ocr_tool = ocr_tool
        self._ocr_disabled_logged = False

    def run(self, rect: tuple[int, int, int, int]) -> TaskResult:
        """
        执行地块巡查流程，按照物理排列顺序依次点击收集信息。
        列顺序为：1-4 1-3 1-2 1-1 2-1， 6-1 5-1 4-1 3-1
        ---------------1-1---------
        ------------2-1---1-2------
        ---------3-1---2-2---1-3---
        ------4-1---3-2---2-3---1-4
        ---5-1---4-2---3-3---2-4---
        6-1---5-2---4-3---3-4------
        ---6-2---5-3---4-4---------
        ------6-3---5-4------------
        ---------6-4---------------
        """
        _ = rect
        logger.info('地块巡查: 开始')
        self.ui.ui_ensure(page_main)
        # self.ui.device.click_button(GOTO_MAIN)

        try:
            for _ in range(2):
                self.ui.device.swipe(LAND_SCAN_SWIPE_H_P1, LAND_SCAN_SWIPE_H_P2, speed=30)
                self.ui.device.sleep(0.5)
            cells_after_left = self._collect_land_cells()
            if not cells_after_left:
                logger.warning('地块巡查: 未识别到地块网格，跳过任务')
                return self.fail('未识别到地块网格')
            cells_after_left = self._exclude_expand_brand_related_cells(cells_after_left)
            self._scan_cells_by_physical_columns(
                cells_after_left, from_side='right', column_count=LAND_SCAN_LEFT_STAGE_COL_COUNT
            )

            for _ in range(2):
                self.ui.device.swipe(LAND_SCAN_SWIPE_H_P2, LAND_SCAN_SWIPE_H_P1, speed=30)
                self.ui.device.sleep(0.5)
            cells_after_right = self._collect_land_cells()
            if not cells_after_right:
                logger.warning('地块巡查: 未识别到地块网格，跳过任务')
                return self.fail('未识别到地块网格')
            cells_after_right = self._exclude_expand_brand_related_cells(cells_after_right)
            self._scan_cells_by_physical_columns(
                cells_after_right, from_side='left', column_count=LAND_SCAN_RIGHT_STAGE_COL_COUNT
            )
        finally:
            # TODO 画面回正
            self.ui.ui_ensure(page_main)

        logger.info('地块巡查: 结束')
        return self.ok()

    def _scan_cells_by_physical_columns(self, cells: list[LandCell], *, from_side: str, column_count: int):
        """按画面物理列扫描地块（列内顺序：从上到下）。"""
        col_map: dict[int, list[LandCell]] = {}
        for cell in cells:
            physical_col = self._physical_col_rtl(cell)
            col_map.setdefault(physical_col, []).append(cell)

        rtl_cols = sorted(col_map.keys())
        if str(from_side).strip().lower() == 'left':
            scan_cols = list(reversed(rtl_cols))[: max(0, int(column_count))]
        else:
            scan_cols = rtl_cols[: max(0, int(column_count))]

        logger.info('地块巡查: 物理列={}', scan_cols)
        for physical_col in scan_cols:
            col_cells = list(col_map.get(physical_col, []))
            col_cells.sort(key=lambda cell: (int(cell.center[1]), int(cell.center[0])))
            for cell in col_cells:
                self._click_and_ocr_cell(cell=cell)
                self.ui.device.click_button(GOTO_MAIN)
                self.ui.device.sleep(0.2)

        return

    def _click_and_ocr_cell(self, *, cell: LandCell):
        """点击单个地块并采集 OCR 文本。"""
        x, y = int(cell.center[0]), int(cell.center[1])
        self.ui.device.click_point(x, y, desc=f'序号 {cell.label}')

        while 1:
            self.ui.device.screenshot()
            # 正常弹窗
            if self.ui.appear(BTN_CROP_REMOVAL, offset=30, static=False) and self.ui.appear(
                BTN_CROP_MATURITY_TIME_SUFFIX, offset=30, static=False
            ):
                break
            # 空土地弹窗
            if self.ui.appear(BTN_LAND_POP_EMPTY, offset=30, threshold=0.65, static=False):
                removal_location = self.ui.appear_location(BTN_LAND_POP_EMPTY, offset=30, threshold=0.65, static=False)
                roi = self._build_land_level_region(removal_location)
                level_items = self.ocr_tool.detect(self.ui.device.image, region=roi, scale=1.2, alpha=1.1, beta=0.0)
                level_text = self._merge_ocr_items_text(level_items)
                level = self._extract_land_level(level_text)
                logger.info(
                    '地块巡查: 空地等级OCR | 序号={} text={} level={}',
                    cell.label,
                    self._short_text(level_text),
                    level or '<empty>',
                )
                if not level:
                    logger.warning('地块巡查: 未解析到地块等级，跳过更新 | 序号={} text={}', cell.label, level_text)
                    return
                updated = self._update_plot_level(plot_id=cell.label, level=level)
                if updated:
                    self._save_land_level_update(plot_id=cell.label, level=level)
                return
            self.ui.device.sleep(0.2)

        # TODO 是否可以升级
        # TODO 识别地块等级
        removal_location = self.ui.appear_location(BTN_CROP_MATURITY_TIME_SUFFIX, offset=30, static=False)
        if removal_location is None:
            logger.warning('地块巡查: 未识别到成熟时间锚点，跳过 OCR | 序号={}', cell.label)
            return
        roi = self._build_ocr_region(removal_location)
        items = self.ocr_tool.detect(self.ui.device.image, region=roi, scale=1.2, alpha=1.1, beta=0.0)
        text, score, tokens = self._pick_time_tokens_near_suffix(items=items, anchor=removal_location)
        countdown = self._extract_maturity_time(text)
        display_text = countdown or text
        logger.debug(
            '地块巡查: OCR筛选 | region={} pick_offset=({}, {}, {}, {}) tokens={} text={}',
            roi,
            LAND_SCAN_TIME_PICK_X1,
            LAND_SCAN_TIME_PICK_Y1,
            LAND_SCAN_TIME_PICK_X2,
            LAND_SCAN_TIME_PICK_Y2,
            tokens,
            display_text or '<empty>',
        )
        logger.info('地块巡查: OCR | 序号={} text={} score={:.3f}', cell.label, self._short_text(display_text), score)
        if countdown:
            updated = self._update_plot_maturity_countdown(plot_id=cell.label, countdown=countdown)
            if updated:
                logger.debug('地块巡查: 成熟时间更新 | 序号={} countdown={}', cell.label, countdown)
                self._save_land_countdown_update(plot_id=cell.label)
        return

    def _collect_land_cells(self) -> list[LandCell]:
        """识别左右锚点并推算地块网格。"""
        self.ui.device.screenshot()
        right_anchor = self.ui.appear_location(BTN_LAND_RIGHT, offset=30, threshold=0.95, static=False)
        left_anchor = self.ui.appear_location(BTN_LAND_LEFT, offset=30, threshold=0.95, static=False)

        cells = get_lands_from_land_anchor(
            right_anchor, left_anchor, rows=LAND_SCAN_ROWS, cols=LAND_SCAN_COLS, start_anchor='right'
        )
        logger.info('地块巡查: 网格识别 | 右锚点={} 左锚点={} 地块总计={}', right_anchor, left_anchor, len(cells))
        return cells

    def _exclude_expand_brand_related_cells(self, cells: list[LandCell]) -> list[LandCell]:
        """按 BTN_EXPAND_BRAND 位置排除不可统计地块。"""
        brand_location = self.ui.appear_location(BTN_EXPAND_BRAND, offset=30, static=False)
        if brand_location is None:
            return cells
        target_cell = self._pick_nearest_cell(cells, brand_location)
        if target_cell is None:
            return cells

        excluded_labels = self._build_expand_brand_excluded_labels(target_cell)
        filtered = [cell for cell in cells if cell.label not in excluded_labels]
        logger.info(
            '地块巡查: 排除未扩建地块 | 排除序号={} 剩余={}/{}', sorted(excluded_labels), len(filtered), len(cells)
        )
        return filtered

    @staticmethod
    def _pick_nearest_cell(cells: list[LandCell], point: tuple[int, int]) -> LandCell | None:
        """返回与 point 距离最近的地块。"""
        if not cells:
            return None
        px = int(point[0])
        py = int(point[1])
        return min(cells, key=lambda cell: (int(cell.center[0]) - px) ** 2 + (int(cell.center[1]) - py) ** 2)

    @staticmethod
    def _build_expand_brand_excluded_labels(cell: LandCell) -> set[str]:
        """构造需排除的序号集合：当前及下方整列、左侧整列。"""
        col = int(cell.col)
        row = int(cell.row)
        labels: set[str] = set()

        # 当前列：从命中行到最下方全部排除（当前 + 下侧）。
        for r in range(row, LAND_SCAN_ROWS + 1):
            labels.add(f'{col}-{r}')

        # 左侧列：整列排除（全行）。
        left_col = col + 1
        if left_col <= LAND_SCAN_COLS:
            for r in range(1, LAND_SCAN_ROWS + 1):
                labels.add(f'{left_col}-{r}')
        return labels

    @staticmethod
    def _physical_col_rtl(cell: LandCell) -> int:
        """将地块映射为物理列索引（右到左，范围 1..9）。"""
        logical_col = int(cell.col)
        logical_row = int(cell.row)
        idx = (LAND_SCAN_ROWS - logical_row) + (logical_col - 1) + 1
        return max(1, min(LAND_SCAN_PHYSICAL_COLS, idx))

    @staticmethod
    def _build_ocr_region(center: tuple[int, int]) -> tuple[int, int, int, int]:
        """以 center 为基准，按固定偏移构造 OCR ROI。"""
        cx = int(center[0])
        cy = int(center[1])
        dx1, dy1, dx2, dy2 = LAND_SCAN_OCR_REGION_OFFSET
        x1 = int(cx + dx1)
        y1 = int(cy + dy1)
        x2 = int(cx + dx2)
        y2 = int(cy + dy2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        x1 = max(0, min(x1, LAND_SCAN_FRAME_WIDTH - 1))
        y1 = max(0, min(y1, LAND_SCAN_FRAME_HEIGHT - 1))
        x2 = max(x1 + 1, min(x2, LAND_SCAN_FRAME_WIDTH))
        y2 = max(y1 + 1, min(y2, LAND_SCAN_FRAME_HEIGHT))
        return x1, y1, x2, y2

    @staticmethod
    def _build_land_level_region(center: tuple[int, int]) -> tuple[int, int, int, int]:
        """以空地弹窗锚点为基准，构造地块等级 OCR ROI。"""
        cx = int(center[0])
        cy = int(center[1])
        dx1, dy1, dx2, dy2 = LAND_SCAN_LEVEL_REGION_OFFSET
        x1 = int(cx + dx1)
        y1 = int(cy + dy1)
        x2 = int(cx + dx2)
        y2 = int(cy + dy2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        x1 = max(0, min(x1, LAND_SCAN_FRAME_WIDTH - 1))
        y1 = max(0, min(y1, LAND_SCAN_FRAME_HEIGHT - 1))
        x2 = max(x1 + 1, min(x2, LAND_SCAN_FRAME_WIDTH))
        y2 = max(y1 + 1, min(y2, LAND_SCAN_FRAME_HEIGHT))
        return x1, y1, x2, y2

    @staticmethod
    def _merge_ocr_items_text(items: list[OCRItem]) -> str:
        """将 OCR items 按 x 坐标拼接为文本。"""
        if not items:
            return ''
        ordered = sorted(items, key=lambda item: min(float(point[0]) for point in item.box))
        return ''.join(str(item.text or '').strip() for item in ordered if str(item.text or '').strip()).strip()

    @staticmethod
    def _extract_land_level(text: str) -> str:
        """从中文 land_level 文本解析配置 level 值。"""
        raw = str(text or '').strip().replace(' ', '')
        if not raw:
            return ''
        match = LAND_SCAN_LEVEL_PATTERN.search(raw)
        if not match:
            return ''
        token = str(match.group(1))
        if token == '未扩建':
            return 'unbuilt'
        if token == '普通':
            return 'normal'
        if token == '红':
            return 'red'
        if token == '黑':
            return 'black'
        if token == '金':
            return 'gold'
        return ''

    @staticmethod
    def _pick_time_tokens_near_suffix(
        items: list[OCRItem],
        anchor: tuple[int, int],
    ) -> tuple[str, float, list[str]]:
        """从 OCR 明细中二次筛选目标窗口内的 token，并按 x 从左到右拼接。"""
        ax = int(anchor[0])
        ay = int(anchor[1])
        x1 = float(ax + LAND_SCAN_TIME_PICK_X1)
        x2 = float(ax + LAND_SCAN_TIME_PICK_X2)
        y1 = float(ay + LAND_SCAN_TIME_PICK_Y1)
        y2 = float(ay + LAND_SCAN_TIME_PICK_Y2)
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        candidates: list[tuple[float, str, float]] = []
        for item in items:
            text = str(item.text or '').strip()
            if not text:
                continue
            xs = [float(point[0]) for point in item.box]
            ys = [float(point[1]) for point in item.box]
            min_x = float(min(xs))
            max_x = float(max(xs))
            min_y = float(min(ys))
            max_y = float(max(ys))
            # 参考好友昵称做法：先拿 OCR item，再按目标窗口做 bbox 筛选。
            if max_x <= x1 or min_x >= x2:
                continue
            if max_y <= y1 or min_y >= y2:
                continue
            candidates.append((min_x, text, float(item.score)))

        candidates.sort(key=lambda row: row[0])
        tokens = [row[1] for row in candidates]
        merged = ''.join(tokens).strip()
        if not candidates:
            return '', 0.0, []
        score = float(sum(row[2] for row in candidates) / len(candidates))
        return merged, score, tokens

    @staticmethod
    def _short_text(text: str, limit: int = 36) -> str:
        """截断 OCR 日志文本，避免日志过长。"""
        clean = str(text or '').strip().replace('\n', ' ')
        if len(clean) <= limit:
            return clean or '<empty>'
        return f'{clean[:limit]}...'

    @staticmethod
    def _extract_maturity_time(text: str) -> str:
        """从 OCR 文本提取 HH:MM:SS。"""
        raw = str(text or '').strip()
        if not raw:
            return ''
        match = LAND_SCAN_MATURITY_TIME_PATTERN.search(raw)
        if not match:
            return ''
        return str(match.group(1))

    def _update_plot_maturity_countdown(self, *, plot_id: str, countdown: str) -> bool:
        """回写单个地块成熟倒计时到配置。"""
        target = str(plot_id or '').strip()
        if not target:
            return False
        land_cfg = getattr(self.engine.config, 'land', None)
        plots = getattr(land_cfg, 'plots', None)
        if not isinstance(plots, list):
            return False

        for item in plots:
            if not isinstance(item, dict):
                continue
            if str(item.get('plot_id', '')).strip() != target:
                continue
            old = str(item.get('maturity_countdown', '') or '').strip()
            if old == countdown:
                return False
            item['maturity_countdown'] = countdown
            return True
        return False

    def _update_plot_level(self, *, plot_id: str, level: str) -> bool:
        """回写单个地块等级到配置。"""
        target = str(plot_id or '').strip()
        normalized_level = str(level or '').strip().lower()
        if not target or not normalized_level:
            return False
        land_cfg = getattr(self.engine.config, 'land', None)
        plots = getattr(land_cfg, 'plots', None)
        if not isinstance(plots, list):
            return False

        for item in plots:
            if not isinstance(item, dict):
                continue
            if str(item.get('plot_id', '')).strip() != target:
                continue
            old = str(item.get('level', '') or '').strip().lower()
            if old == normalized_level:
                return False
            item['level'] = normalized_level
            return True
        return False

    def _save_land_countdown_update(self, *, plot_id: str) -> None:
        """单地块更新后立即落盘。"""
        try:
            self.engine.config.save()
        except Exception as exc:
            logger.warning('地块巡查: 成熟时间写入配置失败 | 序号={} error={}', plot_id, exc)
            return
        self._emit_config_snapshot()
        logger.debug(
            '地块巡查: 成熟时间已写入配置 | 序号={} path={}',
            plot_id,
            self._get_config_path_for_log(),
        )

    def _save_land_level_update(self, *, plot_id: str, level: str) -> None:
        """单地块等级更新后立即落盘。"""
        try:
            self.engine.config.save()
        except Exception as exc:
            logger.warning('地块巡查: 地块等级写入配置失败 | 序号={} level={} error={}', plot_id, level, exc)
            return
        self._emit_config_snapshot()
        logger.debug(
            '地块巡查: 地块等级已写入配置 | 序号={} level={} path={}',
            plot_id,
            level,
            self._get_config_path_for_log(),
        )

    def _emit_config_snapshot(self) -> None:
        """写盘后主动推送一次配置快照，避免 UI 长时间持有旧数据。"""
        emitter = getattr(self.engine, '_emit_config_now', None)
        if callable(emitter):
            try:
                emitter()
            except Exception:
                return

    def _get_config_path_for_log(self) -> str:
        """返回当前配置路径，便于日志排查写入目标。"""
        path = str(getattr(getattr(self.engine, 'config', None), '_config_path', '') or '').strip()
        return path or '<empty>'
