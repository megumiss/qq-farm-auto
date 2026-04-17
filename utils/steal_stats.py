"""好友偷取统计 CSV 工具（一天一行，按实例隔离）。"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from utils.app_paths import instance_dir


def _csv_path(instance_id: str) -> Path:
    p = instance_dir(instance_id) / 'stats'
    p.mkdir(parents=True, exist_ok=True)
    return p / 'steal_stats.csv'


def _safe_int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value or default).strip())
    except Exception:
        return int(default)


def record_steal(instance_id: str, coin_amount: int, bean_amount: int = 0) -> None:
    today = date.today().isoformat()
    path = _csv_path(instance_id)
    rows: dict[str, tuple[int, int]] = {}

    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                day = str(row.get('date') or '').strip()
                if not day:
                    continue
                coin = _safe_int(row.get('count'), 0)
                bean = _safe_int(row.get('bean_count'), 0)
                rows[day] = (coin, bean)

    old_coin, old_bean = rows.get(today, (0, 0))
    rows[today] = (
        old_coin + max(0, int(coin_amount)),
        old_bean + max(0, int(bean_amount)),
    )

    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'count', 'bean_count'])
        writer.writeheader()
        for d, (coin, bean) in sorted(rows.items()):
            writer.writerow({'date': d, 'count': coin, 'bean_count': bean})


def load_stats(instance_id: str, days: int = 30) -> list[tuple[str, int, int]]:
    path = _csv_path(instance_id)
    rows: dict[str, tuple[int, int]] = {}
    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                day = str(row.get('date') or '').strip()
                if not day:
                    continue
                coin = _safe_int(row.get('count'), 0)
                bean = _safe_int(row.get('bean_count'), 0)
                rows[day] = (coin, bean)

    today = date.today()
    return [
        (
            (today - timedelta(days=days - 1 - i)).isoformat(),
            rows.get((today - timedelta(days=days - 1 - i)).isoformat(), (0, 0))[0],
            rows.get((today - timedelta(days=days - 1 - i)).isoformat(), (0, 0))[1],
        )
        for i in range(days)
    ]
