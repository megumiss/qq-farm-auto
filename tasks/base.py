"""任务基类：统一任务上下文类型声明。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from loguru import logger

from core.engine.task.registry import TaskResult

if TYPE_CHECKING:
    from core.engine.bot.local_engine import LocalBotEngine
    from core.ui.ui import UI


class TaskBase:
    """统一持有 `engine/ui`，用于 IDE 静态跳转与补全。"""

    engine: 'LocalBotEngine'
    ui: 'UI'

    def __init__(self, engine: 'LocalBotEngine', ui: 'UI'):
        self.engine = engine
        self.ui = ui

    def get_features(self, task_name: str) -> dict[str, Any]:
        """获取任务特性开关字典。"""
        return self.engine.get_task_features(task_name)

    def is_task_enabled(self, task_name: str) -> bool:
        """按任务名读取调度启用状态。"""
        tasks_cfg = getattr(getattr(self.engine, 'config', None), 'tasks', None)
        if tasks_cfg is None:
            return False
        if isinstance(tasks_cfg, dict):
            cfg = tasks_cfg.get(str(task_name))
        else:
            cfg = getattr(tasks_cfg, str(task_name), None)
        return bool(getattr(cfg, 'enabled', False))

    @staticmethod
    def has_feature(features: Mapping[str, Any] | None, key: str, default: bool = False) -> bool:
        """读取特性开关并归一化为 bool。"""
        if not isinstance(features, Mapping):
            return bool(default)
        return bool(features.get(str(key), default))

    def is_feature_enabled(self, task_name: str, key: str, default: bool = False) -> bool:
        """按任务名读取某个特性开关。"""
        return self.has_feature(self.get_features(task_name), key, default=default)

    @staticmethod
    def parse_truthy(value: Any) -> bool:
        """将常见配置值解析为布尔值。"""
        if isinstance(value, bool):
            return value
        text = str(value or '').strip().lower()
        return text in {'1', 'true', 'yes', 'y', 'on'}

    @staticmethod
    def parse_model_item(item: Any) -> dict[str, Any]:
        """将配置项解析为字典副本。"""
        if isinstance(item, dict):
            return dict(item)
        try:
            dumped = item.model_dump()
        except Exception:
            dumped = {}
        return dumped if isinstance(dumped, dict) else {}

    def parse_land_detail_plots(self) -> list[dict[str, Any]]:
        """解析土地详情 `config.land.plots`。"""
        plots_raw = getattr(getattr(self.engine.config, 'land', None), 'plots', [])
        if not isinstance(plots_raw, list) or not plots_raw:
            return []

        parsed: list[dict[str, Any]] = []
        for idx, raw in enumerate(plots_raw, start=1):
            item = self.parse_model_item(raw)
            if not item:
                continue
            item['source_index'] = int(item.get('source_index') or idx)
            item['plot_id'] = str(item.get('plot_id', '') or '').strip()
            parsed.append(item)
        return parsed

    def parse_land_detail_plots_by_flag(self, flag: str, default: bool = False) -> list[dict[str, Any]]:
        """按布尔标记过滤土地详情地块。"""
        key = str(flag or '').strip()
        if not key:
            return []
        return [item for item in self.parse_land_detail_plots() if self.parse_truthy(item.get(key, default))]

    def collect_land_targets_by_flag(
        self,
        flag: str,
        *,
        anchor_threshold: float = 0.95,
        log_prefix: str = '土地流程',
    ) -> list[tuple[str, tuple[int, int]]]:
        """按土地详情标记收集地块坐标。"""
        pending_entries = self.parse_land_detail_plots_by_flag(flag)
        if not pending_entries:
            return []

        from core.ui.assets import BTN_LAND_LEFT, BTN_LAND_RIGHT
        from utils.land_grid import get_lands_from_land_anchor

        self.ui.device.screenshot()
        land_right_anchor = self.ui.appear_location(
            BTN_LAND_RIGHT,
            offset=30,
            threshold=float(anchor_threshold),
            static=False,
        )
        land_left_anchor = self.ui.appear_location(
            BTN_LAND_LEFT,
            offset=30,
            threshold=float(anchor_threshold),
            static=False,
        )
        if land_right_anchor is None and land_left_anchor is None:
            logger.warning('{}: 未识别到地块锚点，跳过本轮', log_prefix)
            return []

        all_lands = get_lands_from_land_anchor(
            (int(land_right_anchor[0]), int(land_right_anchor[1])) if land_right_anchor is not None else None,
            (int(land_left_anchor[0]), int(land_left_anchor[1])) if land_left_anchor is not None else None,
        )
        if not all_lands:
            logger.warning('{}: 未生成地块网格，跳过本轮', log_prefix)
            return []

        center_by_plot_id = {str(cell.label): (int(cell.center[0]), int(cell.center[1])) for cell in all_lands}
        center_by_order = {int(cell.order): (int(cell.center[0]), int(cell.center[1])) for cell in all_lands}

        targets: list[tuple[str, tuple[int, int]]] = []
        missing_refs: list[str] = []
        for item in pending_entries:
            plot_id = str(item.get('plot_id', '') or '').strip()
            if plot_id and plot_id in center_by_plot_id:
                targets.append((plot_id, center_by_plot_id[plot_id]))
                continue

            try:
                order = int(item.get('order', 0))
            except Exception:
                order = 0
            if order <= 0:
                try:
                    order = int(item.get('source_index', 0))
                except Exception:
                    order = 0
            point = center_by_order.get(order)
            if point is None:
                missing_refs.append(plot_id or f'order:{order}')
                continue
            targets.append((plot_id or f'order:{order}', point))

        target_refs = [ref for ref, _ in targets]
        logger.info('{}: 地块序号={}', log_prefix, target_refs)
        if missing_refs:
            logger.warning('{}: 未映射地块={}', log_prefix, missing_refs)
        return targets

    def backfill_land_flag_false(
        self,
        plot_refs: list[str],
        flag: str,
        *,
        log_prefix: str = '土地流程',
    ) -> None:
        """按地块序号回填土地标记为 `false`。"""
        key = str(flag or '').strip()
        if not key:
            return

        plot_ids = {str(ref).strip() for ref in plot_refs if '-' in str(ref)}
        if not plot_ids:
            return

        plots = getattr(getattr(self.engine.config, 'land', None), 'plots', None)
        if not isinstance(plots, list):
            return

        changed_plot_ids: list[str] = []
        for item in plots:
            if not isinstance(item, dict):
                continue
            plot_id = str(item.get('plot_id', '') or '').strip()
            if plot_id not in plot_ids:
                continue
            if not self.parse_truthy(item.get(key, False)):
                continue
            item[key] = False
            changed_plot_ids.append(plot_id)

        if not changed_plot_ids:
            return

        try:
            self.engine.config.save()
        except Exception as exc:
            logger.warning('{}: 状态回填失败 | flag={} error={}', log_prefix, key, exc)
            return

        emit_now = getattr(self.engine, '_emit_config_now', None)
        if callable(emit_now):
            try:
                emit_now()
            except Exception:
                pass
        logger.info('{}: 状态回填完成 | flag={} plots={}', log_prefix, key, sorted(changed_plot_ids))

    @staticmethod
    def ok(*, next_run_seconds: int | None = None) -> TaskResult:
        """构造成功结果。"""
        return TaskResult(success=True, next_run_seconds=next_run_seconds, error='')

    @staticmethod
    def fail(error: str, *, next_run_seconds: int | None = None) -> TaskResult:
        """构造失败结果。"""
        return TaskResult(
            success=False,
            next_run_seconds=next_run_seconds,
            error=str(error or ''),
        )
