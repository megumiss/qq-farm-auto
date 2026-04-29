"""生成演示用统计假数据。"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.app_paths import instance_dir


def _stats_dir(instance_id: str) -> Path:
    path = instance_dir(instance_id) / 'stats'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _date_series(days: int) -> list[date]:
    today = date.today()
    return [today - timedelta(days=days - 1 - i) for i in range(days)]


def _build_rows(days: int, seed: int) -> tuple[list[dict[str, int | str]], list[dict[str, int | str]]]:
    rng = random.Random(seed)
    steal_rows: list[dict[str, int | str]] = []
    action_rows: list[dict[str, int | str]] = []
    for day in _date_series(days):
        weekday = day.weekday()
        weekend_boost = 1.25 if weekday >= 5 else 1.0
        active_scale = rng.uniform(0.75, 1.35) * weekend_boost

        harvest = int(max(5, rng.gauss(85, 30) * active_scale))
        operation = int(max(harvest + 10, harvest + rng.gauss(55, 18) * active_scale))
        friend_steal = int(max(0, rng.gauss(22, 10) * active_scale))
        friend_help = int(max(0, rng.gauss(28, 12) * active_scale))

        coin = int(max(0, friend_steal * rng.uniform(900, 2800) + rng.uniform(1500, 12000)))
        bean = int(max(0, friend_steal * rng.uniform(2, 11) + rng.uniform(5, 70)))

        day_text = day.isoformat()
        steal_rows.append(
            {
                'date': day_text,
                'count': coin,
                'bean_count': bean,
            }
        )
        action_rows.append(
            {
                'date': day_text,
                'harvest': harvest,
                'operation': operation,
                'friend_steal': friend_steal,
                'friend_help': friend_help,
            }
        )
    return steal_rows, action_rows


def _write_csv(path: Path, *, fieldnames: list[str], rows: list[dict[str, int | str]]) -> None:
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description='生成数据统计页演示用假数据')
    parser.add_argument('--instance-id', default='default', help='实例ID，默认 default')
    parser.add_argument('--days', type=int, default=60, help='生成天数，默认 60')
    parser.add_argument('--seed', type=int, default=20260428, help='随机种子，默认 20260428')
    args = parser.parse_args()

    days = max(1, int(args.days))
    instance_id = str(args.instance_id or 'default').strip() or 'default'
    seed = int(args.seed)

    stats_dir = _stats_dir(instance_id)
    steal_rows, action_rows = _build_rows(days=days, seed=seed)
    steal_csv = stats_dir / 'steal_stats.csv'
    action_csv = stats_dir / 'daily_action_stats.csv'
    _write_csv(
        steal_csv,
        fieldnames=['date', 'count', 'bean_count'],
        rows=steal_rows,
    )
    _write_csv(
        action_csv,
        fieldnames=['date', 'harvest', 'operation', 'friend_steal', 'friend_help'],
        rows=action_rows,
    )

    print(f'已生成假数据: {instance_id}')
    print(f'- {steal_csv}')
    print(f'- {action_csv}')
    print(f'- days={days}, seed={seed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
