"""Fluent 日志面板。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import QTextEdit
from qfluentwidgets import isDarkTheme, qconfig


class LogPanel(QTextEdit):
    """运行日志窗口。"""

    MAX_LINES = 500

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('runtimeLogPanel')
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setPlaceholderText('运行后显示日志...')
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.document().setMaximumBlockCount(self.MAX_LINES)
        font = QFont('Cascadia Code')
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(8)
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
            text = '#1e293b'
            border = 'rgba(15, 23, 42, 0.12)'
            bg = '#f8fafc'
            selection = 'rgba(59, 130, 246, 0.24)'
            sb_handle = 'rgba(100, 116, 139, 0.36)'
            sb_handle_hover = 'rgba(100, 116, 139, 0.58)'

        self.setStyleSheet(
            f"""
QTextEdit#runtimeLogPanel {{
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

    @staticmethod
    def _resolve_level_color(message: str, *, dark: bool) -> str:
        raw = str(message or '')
        text_upper = raw.upper()
        if 'ERROR' in text_upper or 'CRITICAL' in text_upper or '✗' in raw or '✘' in raw:
            return '#f87171' if dark else '#dc2626'
        if 'WARNING' in text_upper or 'WARN' in text_upper:
            return '#fbbf24' if dark else '#d97706'
        if 'SUCCESS' in text_upper or '✓' in raw:
            return '#4ade80' if dark else '#16a34a'
        if 'INFO' in text_upper:
            return '#60a5fa' if dark else '#2563eb'
        if 'DEBUG' in text_upper or 'TRACE' in text_upper:
            return '#94a3b8' if dark else '#64748b'
        return '#cbd5e1' if dark else '#475569'

    def append_log(self, message: str) -> None:
        text = str(message or '').rstrip()
        if not text:
            return
        color = QColor(self._resolve_level_color(text, dark=isDarkTheme()))
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        cursor.insertText(text, fmt)
        cursor.insertBlock()
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
