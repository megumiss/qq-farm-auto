"""Fluent 日志面板。"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from qfluentwidgets import PlainTextEdit, isDarkTheme, qconfig


class LogPanel(PlainTextEdit):
    """运行日志窗口。"""

    MAX_LINES = 600

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('runtimeLogPanel')
        self.setReadOnly(True)
        self.setPlaceholderText('运行后显示日志...')
        self.setLineWrapMode(PlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.document().setMaximumBlockCount(self.MAX_LINES)
        font = QFont('Cascadia Mono')
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self._apply_style()
        qconfig.themeChangedFinished.connect(self._apply_style)

    def _apply_style(self, *_args) -> None:
        if isDarkTheme():
            text = '#e5e7eb'
            border = 'rgba(255, 255, 255, 0.16)'
            bg = 'rgba(18, 18, 20, 0.86)'
            selection = 'rgba(59, 130, 246, 0.45)'
            sb_handle = 'rgba(148, 163, 184, 0.46)'
            sb_handle_hover = 'rgba(148, 163, 184, 0.68)'
        else:
            text = '#0f172a'
            border = 'rgba(15, 23, 42, 0.12)'
            bg = 'rgba(248, 250, 252, 0.92)'
            selection = 'rgba(59, 130, 246, 0.24)'
            sb_handle = 'rgba(100, 116, 139, 0.36)'
            sb_handle_hover = 'rgba(100, 116, 139, 0.58)'

        self.setStyleSheet(
            f"""
QPlainTextEdit#runtimeLogPanel {{
    color: {text};
    background-color: {bg};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: {selection};
}}
QScrollBar:vertical {{
    width: 10px;
    background: transparent;
    margin: 4px 2px 4px 2px;
}}
QScrollBar::handle:vertical {{
    min-height: 24px;
    border-radius: 4px;
    background: {sb_handle};
}}
QScrollBar::handle:vertical:hover {{
    background: {sb_handle_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
        )

    def append_log(self, message: str) -> None:
        text = str(message or '').rstrip()
        if not text:
            return
        now = datetime.now().strftime('%H:%M:%S')
        self.appendPlainText(f'[{now}] {text}')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
