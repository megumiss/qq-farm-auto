"""Fluent 状态面板。"""

from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ElevatedCardWidget,
    FluentIcon,
    IconWidget,
    StrongBodyLabel,
)


class StatusPanel(QWidget):
    """运行态统计显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict[str, StrongBodyLabel] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        runtime_card, runtime_grid = self._build_card('运行状态', FluentIcon.ROBOT)
        self._add_cell(runtime_grid, 0, 0, '状态', 'state', '空闲')
        self._add_cell(runtime_grid, 0, 1, '已运行', 'elapsed', '--')
        self._add_cell(runtime_grid, 0, 2, '平台', 'platform', '--')
        self._add_cell(runtime_grid, 0, 3, '窗口ID', 'window_id', '--')
        root.addWidget(runtime_card)

        tasks_card, tasks_grid = self._build_card('任务队列', FluentIcon.CALENDAR)
        self._add_cell(tasks_grid, 0, 0, '当前任务', 'current_task', '--')
        self._add_cell(tasks_grid, 0, 1, '运行中', 'running_tasks', '0')
        self._add_cell(tasks_grid, 0, 2, '待执行', 'pending_tasks', '0')
        self._add_cell(tasks_grid, 0, 3, '等待中', 'waiting_tasks', '0')
        self._add_cell(tasks_grid, 1, 0, '下一任务', 'next_task', '--')
        self._add_cell(tasks_grid, 1, 1, '下次执行', 'next_run', '--')
        root.addWidget(tasks_card)

        stats_card, stats_grid = self._build_card('动作统计', FluentIcon.APPLICATION)
        self._add_cell(stats_grid, 0, 0, '收获', 'harvest', '0')
        self._add_cell(stats_grid, 0, 1, '播种', 'plant', '0')
        self._add_cell(stats_grid, 0, 2, '浇水', 'water', '0')
        self._add_cell(stats_grid, 1, 0, '除草', 'weed', '0')
        self._add_cell(stats_grid, 1, 1, '除虫', 'bug', '0')
        self._add_cell(stats_grid, 1, 2, '出售', 'sell', '0')
        root.addWidget(stats_card)

    def _build_card(self, title: str, icon: FluentIcon) -> tuple[ElevatedCardWidget, QGridLayout]:
        card = ElevatedCardWidget(self)
        card.setObjectName('statusCard')
        card.setStyleSheet(
            'ElevatedCardWidget#statusCard { border-radius: 10px; }'
            'ElevatedCardWidget#statusCard:hover { background-color: rgba(37, 99, 235, 0.04); }'
        )
        wrapper = QVBoxLayout(card)
        wrapper.setContentsMargins(12, 10, 12, 10)
        wrapper.setSpacing(8)

        header = QWidget(card)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        icon_widget = IconWidget(icon, header)
        icon_widget.setFixedSize(14, 14)
        header_layout.addWidget(icon_widget)
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)
        title_col.addWidget(BodyLabel(title))
        header_layout.addLayout(title_col)
        header_layout.addStretch()
        wrapper.addWidget(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        wrapper.addLayout(grid)
        return card, grid

    def _add_cell(self, grid: QGridLayout, row: int, col: int, title: str, key: str, default: str) -> None:
        row_widget = QWidget(self)
        row_widget.setObjectName('statusItem')
        row_widget.setStyleSheet('QWidget#statusItem { border: none; border-radius: 6px; background: transparent; }')
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 2, 6, 2)
        row_layout.setSpacing(6)
        title_label = CaptionLabel(f'{title}:')
        title_label.setTextColor(QColor('#64748B'), QColor('#94A3B8'))
        row_layout.addWidget(title_label)
        value = StrongBodyLabel(default)
        value.setTextColor(QColor('#0F172A'), QColor('#E5E7EB'))
        row_layout.addWidget(value)
        row_layout.addStretch()
        grid.addWidget(row_widget, row, col)
        self._labels[key] = value

    def _set_value(self, key: str, value: str) -> None:
        label = self._labels[key]
        text = str(value)
        label.setText(text)
        label.setToolTip(text)

    def update_stats(self, stats: dict) -> None:
        state = str(stats.get('state', 'idle'))
        color = {
            'idle': '#6b7280',
            'running': '#16a34a',
            'paused': '#d97706',
            'error': '#dc2626',
        }.get(state, '#2563eb')
        state_text = {
            'idle': '空闲',
            'running': '运行中',
            'paused': '已暂停',
            'error': '异常',
        }.get(state, state)
        self._labels['state'].setText(state_text)
        self._labels['state'].setToolTip(state_text)
        state_color = QColor(color)
        self._labels['state'].setTextColor(state_color, state_color)
        self._set_value('elapsed', stats.get('elapsed', '--'))
        self._set_value('platform', stats.get('current_platform', '--'))
        self._set_value('window_id', stats.get('window_id', '--'))
        self._set_value('current_task', stats.get('current_task', '--'))
        self._set_value('running_tasks', stats.get('running_tasks', 0))
        self._set_value('pending_tasks', stats.get('pending_tasks', 0))
        self._set_value('waiting_tasks', stats.get('waiting_tasks', 0))
        self._set_value('next_task', stats.get('next_task', '--'))
        self._set_value('next_run', stats.get('next_run', '--'))
        self._labels['running_tasks'].setTextColor(QColor('#16A34A'), QColor('#4ADE80'))
        self._labels['pending_tasks'].setTextColor(QColor('#2563EB'), QColor('#60A5FA'))
        self._labels['waiting_tasks'].setTextColor(QColor('#D97706'), QColor('#FBBF24'))
        for key in ('harvest', 'plant', 'water', 'weed', 'bug', 'sell'):
            self._set_value(key, stats.get(key, 0))
