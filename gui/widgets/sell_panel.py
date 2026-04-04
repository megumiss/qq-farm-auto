"""出售设置面板 - 仅保留批量出售"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from models.config import AppConfig, SellMode


class SellPanel(QWidget):
    """承载 `SellPanel` 相关界面控件与交互逻辑。"""
    config_changed = pyqtSignal(object)

    def __init__(self, config: AppConfig, parent=None):
        """初始化对象并准备运行所需状态。"""
        super().__init__(parent)
        self.config = config
        self._init_ui()
        self._force_batch_mode()

    def _init_ui(self):
        """初始化 `ui` 相关状态或界面。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        group = QGroupBox("出售设置")
        
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 6, 0, 0)
        inner_layout.setSpacing(10)

        title = QLabel('出售模式')
        title.setStyleSheet('font-weight: 600; color: #1e293b;')
        inner_layout.addWidget(title)

        desc = QLabel('当前版本仅支持批量出售。任务售卖会自动执行“批量出售 -> 确认出售”。')
        desc.setStyleSheet('color: #64748b;')
        desc.setWordWrap(True)
        inner_layout.addWidget(desc)
        inner_layout.addStretch(1)

        group.setLayout(inner_layout)
        layout.addWidget(group)
        layout.addStretch(1)

    def _force_batch_mode(self):
        """执行 `force batch mode` 相关处理。"""
        if self.config.sell.mode != SellMode.BATCH_ALL:
            self.config.sell.mode = SellMode.BATCH_ALL
            self.config.save()
            self.config_changed.emit(self.config)
