"""任务基类：统一任务上下文类型声明与强类型参数访问。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger

from core.engine.task.registry import TaskResult
from models.config import AppConfig
from models.task_views import (
    FriendTaskView,
    GiftTaskView,
    LandScanTaskView,
    MainTaskView,
    RewardTaskView,
    SellTaskView,
    ShareTaskView,
)

if TYPE_CHECKING:
    from core.engine.bot.local_engine import LocalBotEngine
    from core.ui.ui import UI


@dataclass(slots=True)
class TaskViews:
    """任务强类型视图入口。"""

    owner: 'TaskBase'

    @property
    def main(self) -> MainTaskView:
        return self.owner.engine.build_task_view('main')  # type: ignore[return-value]

    @property
    def friend(self) -> FriendTaskView:
        return self.owner.engine.build_task_view('friend')  # type: ignore[return-value]

    @property
    def gift(self) -> GiftTaskView:
        return self.owner.engine.build_task_view('gift')  # type: ignore[return-value]

    @property
    def reward(self) -> RewardTaskView:
        return self.owner.engine.build_task_view('reward')  # type: ignore[return-value]

    @property
    def share(self) -> ShareTaskView:
        return self.owner.engine.build_task_view('share')  # type: ignore[return-value]

    @property
    def sell(self) -> SellTaskView:
        return self.owner.engine.build_task_view('sell')  # type: ignore[return-value]

    @property
    def land_scan(self) -> LandScanTaskView:
        return self.owner.engine.build_task_view('land_scan')  # type: ignore[return-value]


class TaskBase:
    """统一持有 `engine/ui`，用于 IDE 静态跳转与补全。"""

    engine: 'LocalBotEngine'
    ui: 'UI'

    def __init__(self, engine: 'LocalBotEngine', ui: 'UI'):
        self.engine = engine
        self.ui = ui
        self.task = TaskViews(self)

    @property
    def config(self) -> AppConfig:
        """当前实例完整配置（强类型）。"""
        return self.engine.config

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
        plots_raw = self.config.land.plots
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

        plots = self.config.land.plots
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
            self.config.save()
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
        return TaskResult(success=False, next_run_seconds=next_run_seconds, error=str(error or ''))
