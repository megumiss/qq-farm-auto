"""好友偷取统计图表面板。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CardWidget, SegmentedWidget, isDarkTheme

from utils.steal_stats import load_stats


def _format_count(value: int) -> str:
    if value >= 100_000_000:
        text = f'{value / 100_000_000:.2f}'.rstrip('0').rstrip('.')
        return f'{text}亿'
    if value >= 10_000:
        text = f'{value / 10_000:.2f}'.rstrip('0').rstrip('.')
        return f'{text}万'
    return str(value)


def _format_date_label(date_text: str) -> str:
    return date_text[5:] if len(date_text) >= 10 else date_text


class _BarChart(QWidget):
    def __init__(self, on_wheel: Callable[[int], None], *, bar_color: str, parent=None):
        super().__init__(parent)
        self._on_wheel = on_wheel
        self._bar_color = QColor(bar_color)
        self._data: list[tuple[str, int]] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(140)

    def set_data(self, data: list[tuple[str, int]]):
        self._data = data
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pad_l, pad_r, pad_t, pad_b = 56, 16, 16, 52
        w = self.width() - pad_l - pad_r
        h = self.height() - pad_t - pad_b
        n = len(self._data)
        max_val = max(v for _, v in self._data) or 1

        dark = isDarkTheme()
        fg = QColor('#e2e8f0' if dark else '#1e293b')
        grid_c = QColor('#334155' if dark else '#e2e8f0')
        bar_c = self._bar_color

        font = QFont()
        font.setPointSize(8)
        p.setFont(font)

        for i in range(5):
            y = pad_t + h - i * h // 4
            p.setPen(QPen(grid_c, 1, Qt.PenStyle.DashLine))
            p.drawLine(pad_l, y, pad_l + w, y)
            p.setPen(fg)
            p.drawText(
                QRectF(0, y - 10, pad_l - 4, 20),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _format_count(int(max_val * i / 4)),
            )

        bar_w = max(4, w // n - 4)
        for i, (d, v) in enumerate(self._data):
            bh = int(v / max_val * h)
            x = pad_l + i * w // n + (w // n - bar_w) // 2
            y = pad_t + h - bh
            p.setBrush(bar_c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, y, bar_w, bh), 3, 3)

        # 保持底部日期可见，30 天视图按固定间隔抽样，避免标签重叠。
        sample_step = max(1, n // 6)
        for i, (d, _) in enumerate(self._data):
            if i != 0 and i != n - 1 and i % sample_step != 0:
                continue
            x = pad_l + i * w // n + w // n // 2
            p.setPen(grid_c)
            p.drawLine(x, pad_t + h, x, pad_t + h + 4)
            p.setPen(fg)
            p.drawText(
                QRectF(x - 22, pad_t + h + 6, 44, 20),
                Qt.AlignmentFlag.AlignHCenter,
                _format_date_label(d),
            )
        p.end()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta:
            self._on_wheel(1 if delta > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class StealChartPanel(QWidget):
    _MIN_DAY_WINDOW = 1
    _MAX_DAY_WINDOW = 120
    _MIN_WEEK_WINDOW = 1
    _MAX_WEEK_WINDOW = 52

    def __init__(self, instance_id: str = 'default', parent=None):
        super().__init__(parent)
        self._instance_id = instance_id
        self._day_window = 15
        self._week_window = 8
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        ctrl = QHBoxLayout()
        self._seg = SegmentedWidget()
        self._seg.addItem('day', '天视图')
        self._seg.addItem('week', '周视图')
        self._seg.setCurrentItem('day')
        self._seg.currentItemChanged.connect(lambda _: self._refresh())
        ctrl.addWidget(self._seg)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        coin_title = BodyLabel('金币')
        coin_title.setStyleSheet('font-weight: 700;')
        self._coin_chart = _BarChart(self._adjust_window, bar_color='#f59e0b')
        bean_title = BodyLabel('金豆')
        bean_title.setStyleSheet('font-weight: 700;')
        self._bean_chart = _BarChart(self._adjust_window, bar_color='#22c55e')
        card_layout.addWidget(coin_title)
        card_layout.addWidget(self._coin_chart)
        card_layout.addWidget(bean_title)
        card_layout.addWidget(self._bean_chart)
        layout.addWidget(card, 1)

        self._refresh()

    def _adjust_window(self, delta: int):
        if delta == 0:
            return
        is_week = self._seg.currentRouteKey() == 'week'
        if is_week:
            self._week_window = min(
                self._MAX_WEEK_WINDOW,
                max(self._MIN_WEEK_WINDOW, self._week_window + delta),
            )
        else:
            self._day_window = min(
                self._MAX_DAY_WINDOW,
                max(self._MIN_DAY_WINDOW, self._day_window + delta),
            )
        self._refresh()

    def _refresh(self):
        is_week = self._seg.currentRouteKey() == 'week'
        if is_week:
            today = date.today()
            current_monday = today - timedelta(days=today.weekday())
            first_monday = current_monday - timedelta(weeks=self._week_window - 1)
            days = (today - first_monday).days + 1
            day_data = load_stats(self._instance_id, days)
            day_map = {d: (coin, bean) for d, coin, bean in day_data}
            mondays = [first_monday + timedelta(weeks=i) for i in range(self._week_window)]
            data: list[tuple[str, int, int]] = []
            for monday in mondays:
                week_coin_sum = 0
                week_bean_sum = 0
                for offset in range(7):
                    current_day = monday + timedelta(days=offset)
                    if current_day > today:
                        break
                    day_coin, day_bean = day_map.get(current_day.isoformat(), (0, 0))
                    week_coin_sum += day_coin
                    week_bean_sum += day_bean
                data.append((monday.isoformat(), week_coin_sum, week_bean_sum))
        else:
            data = load_stats(self._instance_id, self._day_window)
        self._coin_chart.set_data([(d, coin) for d, coin, _ in data])
        self._bean_chart.set_data([(d, bean) for d, _, bean in data])

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
