"""每日动作统计 CSV 工具（按实例隔离）。"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from utils.app_paths import instance_dir


def _csv_path(instance_id: str) -> Path:
    p = instance_dir(instance_id) / 'stats'
    p.mkdir(parents=True, exist_ok=True)
    return p / 'daily_action_stats.csv'


def _safe_int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value or default).strip())
    except Exception:
        return int(default)


def record_daily_action(
    instance_id: str,
    *,
    harvest: int = 0,
    operation: int = 0,
    friend_steal: int = 0,
    friend_help: int = 0,
) -> None:
    today = date.today().isoformat()
    path = _csv_path(instance_id)
    rows: dict[str, tuple[int, int, int, int]] = {}

    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                day = str(row.get('date') or '').strip()
                if not day:
                    continue
                rows[day] = (
                    _safe_int(row.get('harvest'), 0),
                    _safe_int(row.get('operation'), 0),
                    _safe_int(row.get('friend_steal'), 0),
                    _safe_int(row.get('friend_help'), 0),
                )

    old_harvest, old_operation, old_friend_steal, old_friend_help = rows.get(today, (0, 0, 0, 0))
    rows[today] = (
        old_harvest + max(0, int(harvest)),
        old_operation + max(0, int(operation)),
        old_friend_steal + max(0, int(friend_steal)),
        old_friend_help + max(0, int(friend_help)),
    )

    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=['date', 'harvest', 'operation', 'friend_steal', 'friend_help'],
        )
        writer.writeheader()
        for d, (harvest_count, operation_count, friend_steal_count, friend_help_count) in sorted(rows.items()):
            writer.writerow(
                {
                    'date': d,
                    'harvest': harvest_count,
                    'operation': operation_count,
                    'friend_steal': friend_steal_count,
                    'friend_help': friend_help_count,
                }
            )


def load_daily_actions(instance_id: str, days: int = 30) -> list[tuple[str, int, int, int, int]]:
    path = _csv_path(instance_id)
    rows: dict[str, tuple[int, int, int, int]] = {}
    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                day = str(row.get('date') or '').strip()
                if not day:
                    continue
                rows[day] = (
                    _safe_int(row.get('harvest'), 0),
                    _safe_int(row.get('operation'), 0),
                    _safe_int(row.get('friend_steal'), 0),
                    _safe_int(row.get('friend_help'), 0),
                )

    today = date.today()
    out: list[tuple[str, int, int, int, int]] = []
    for i in range(days):
        current_day = (today - timedelta(days=days - 1 - i)).isoformat()
        harvest_count, operation_count, friend_steal_count, friend_help_count = rows.get(current_day, (0, 0, 0, 0))
        out.append((current_day, harvest_count, operation_count, friend_steal_count, friend_help_count))
    return out
