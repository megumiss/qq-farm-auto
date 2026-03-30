"""出售设置面板 - 独立 Tab 页"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QComboBox, QGridLayout, QScrollArea,
)
from PyQt6.QtCore import pyqtSignal

from models.config import AppConfig, SellMode
from models.game_data import CROPS


class SellPanel(QWidget):
    config_changed = pyqtSignal(object)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._loading = True
        self._init_ui()
        self._load_config()
        self._connect_auto_save()
        self._loading = False

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 出售模式（顶部）
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("出售模式:"))
        self._sell_mode_combo = QComboBox()
        self._sell_mode_combo.addItem("批量全部出售", SellMode.BATCH_ALL.value)
        self._sell_mode_combo.addItem("选择性出售", SellMode.SELECTIVE.value)
        self._sell_mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._sell_mode_combo, 1)
        layout.addLayout(mode_row)

        # 全选
        self._cb_select_all = QCheckBox("全选")
        self._cb_select_all.toggled.connect(self._on_select_all)
        layout.addWidget(self._cb_select_all)

        # 作物勾选列表（可滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        crops_container = QWidget()
        grid = QGridLayout(crops_container)
        grid.setSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        self._crop_cbs: dict[str, QCheckBox] = {}
        for i, (name, _, req_level, _, _, _) in enumerate(CROPS):
            cb = QCheckBox(f"{name} (Lv{req_level})")
            self._crop_cbs[name] = cb
            grid.addWidget(cb, i // 3, i % 3)

        scroll.setWidget(crops_container)
        self._scroll = scroll
        layout.addWidget(scroll)
        layout.addStretch(1)

    def _connect_auto_save(self):
        self._sell_mode_combo.currentIndexChanged.connect(self._auto_save)
        for cb in self._crop_cbs.values():
            cb.toggled.connect(self._auto_save)

    def _on_mode_changed(self, index: int):
        is_selective = self._sell_mode_combo.itemData(index) == SellMode.SELECTIVE.value
        self._scroll.setVisible(is_selective)
        self._cb_select_all.setVisible(is_selective)

    def _on_select_all(self, checked: bool):
        self._loading = True
        for cb in self._crop_cbs.values():
            cb.setChecked(checked)
        self._loading = False
        self._auto_save()

    def _auto_save(self):
        if self._loading:
            return
        c = self.config
        c.sell.mode = SellMode(self._sell_mode_combo.currentData())
        c.sell.sell_crops = [name for name, cb in self._crop_cbs.items() if cb.isChecked()]
        c.save()
        self.config_changed.emit(c)

    def _load_config(self):
        c = self.config
        sell_idx = 0 if c.sell.mode == SellMode.BATCH_ALL else 1
        self._sell_mode_combo.setCurrentIndex(sell_idx)
        self._on_mode_changed(sell_idx)
        for name, cb in self._crop_cbs.items():
            cb.setChecked(name in c.sell.sell_crops)
