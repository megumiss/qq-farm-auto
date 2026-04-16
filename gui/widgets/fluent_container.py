"""Fluent 透明容器组件。"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPropertyAnimation
from PyQt6.QtGui import QColor
from qfluentwidgets import CardWidget, ElevatedCardWidget


class TransparentCardContainer(CardWidget):
    """用于滚动区域内容层的无底色 Fluent 容器。"""

    def _normalBackgroundColor(self):
        return QColor(0, 0, 0, 0)

    def _hoverBackgroundColor(self):
        return QColor(0, 0, 0, 0)

    def _pressedBackgroundColor(self):
        return QColor(0, 0, 0, 0)

    def paintEvent(self, _event):
        # 内容容器仅用于布局，不绘制任何卡片底色或边框。
        return


class StableElevatedCardWidget(ElevatedCardWidget):
    """布局安全的 Elevated 卡片，避免回弹到过期坐标导致重叠。"""

    def showEvent(self, event):
        super().showEvent(event)
        self._originalPos = self.pos()

    def moveEvent(self, event):
        super().moveEvent(event)
        ani = getattr(self, 'elevatedAni', None)
        if ani is not None and ani.state() == QPropertyAnimation.State.Running:
            return
        if self.underMouse():
            # 悬浮抬升高度固定为 3px，布局移动后同步“回落基准点”。
            self._originalPos = QPoint(self.pos().x(), self.pos().y() + 3)
        else:
            self._originalPos = self.pos()
