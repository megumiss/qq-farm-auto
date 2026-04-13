"""任务设置面板（按 tasks.<task>.features 生成）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.dialog_styles import UNIFIED_DIALOG_STYLE
from models.config import AppConfig
from utils.app_paths import load_config_json_object
from utils.feature_policy import is_feature_forced_off


class ListFeatureEditorDialog(QDialog):
    """列表型任务功能编辑弹窗。"""

    _EXTRA_STYLE = """
    QLabel#dialogHint {
        color: #64748b;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 8px 10px;
    }
    QListWidget#valueList {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 6px;
        outline: 0;
    }
    QListWidget#valueList::item {
        border: none;
        margin: 2px 0;
        padding: 0;
    }
    QLineEdit#valueInput {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 6px 10px;
        color: #0f172a;
        min-height: 20px;
    }
    QLineEdit#valueInput:focus {
        border-color: #2563eb;
    }
    QWidget#valueRow {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
    }
    QLabel#valueLabel {
        color: #1e293b;
        padding-left: 8px;
    }
    QPushButton#addButton {
        min-width: 0px;
        min-height: 36px;
        border-radius: 8px;
        border: none;
        background: #2563eb;
        color: #ffffff;
        font-weight: 700;
        font-size: 13px;
        padding: 0 20px;
    }
    QPushButton#addButton:hover {
        background: #1d4ed8;
    }
    QPushButton#actionButton {
        min-width: 0px;
        min-height: 36px;
        border-radius: 8px;
        background: #f1f5f9;
        color: #334155;
        border: 1px solid #e2e8f0;
        font-weight: 700;
        font-size: 13px;
        padding: 0 20px;
    }
    QPushButton#actionButton:hover {
        background: #e2e8f0;
        border-color: #cbd5e1;
    }
    QPushButton#saveButton {
        min-width: 0px;
        min-height: 36px;
        border-radius: 8px;
        border: none;
        background: #16a34a;
        color: #ffffff;
        font-weight: 700;
        font-size: 13px;
        padding: 0 20px;
    }
    QPushButton#saveButton:hover {
        background: #15803d;
    }
    QPushButton#deleteItemButton {
        min-width: 0px;
        min-height: 30px;
        border-radius: 8px;
        border: none;
        background: #dc2626;
        color: #ffffff;
        font-weight: 700;
        font-size: 13px;
        padding: 0 12px;
    }
    QPushButton#deleteItemButton:hover {
        background: #b91c1c;
    }
    QScrollBar:vertical {
        background: #f5f5f7;
        width: 6px;
        border-radius: 3px;
    }
    QScrollBar::handle:vertical {
        background: #cbd5e1;
        border-radius: 3px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #94a3b8;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    """

    def __init__(
        self,
        *,
        title: str,
        values: list[str],
        add_text: str,
        delete_text: str,
        save_text: str,
        cancel_text: str,
        input_placeholder: str,
        hint_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName('listFeatureEditorDialog')
        self.setWindowTitle(title)
        self.resize(420, 460)
        self._delete_text = str(delete_text or '删除')
        self.setStyleSheet(f'{UNIFIED_DIALOG_STYLE}\n{self._EXTRA_STYLE}')

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        hint = QLabel(hint_text)
        hint.setObjectName('dialogHint')
        hint.setWordWrap(True)
        root.addWidget(hint)

        self._list = QListWidget(self)
        self._list.setObjectName('valueList')
        root.addWidget(self._list, 1)

        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.setSpacing(8)
        self._input = QLineEdit(self)
        self._input.setObjectName('valueInput')
        self._input.setPlaceholderText(input_placeholder)
        add_btn = QPushButton(add_text, self)
        add_btn.setObjectName('addButton')
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._on_add_clicked)
        self._input.returnPressed.connect(self._on_add_clicked)
        add_row.addWidget(self._input, 1)
        add_row.addWidget(add_btn)
        root.addLayout(add_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch()
        cancel_btn = QPushButton(cancel_text, self)
        cancel_btn.setObjectName('actionButton')
        save_btn = QPushButton(save_text, self)
        save_btn.setObjectName('saveButton')
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.accept)
        action_row.addWidget(cancel_btn)
        action_row.addWidget(save_btn)
        root.addLayout(action_row)

        for value in values:
            self._append_item(str(value))

    def _on_add_clicked(self):
        """新增列表项。"""
        text = str(self._input.text() or '').strip()
        if not text:
            return
        existing = {name.lower() for name in self.values()}
        if text.lower() in existing:
            self._input.clear()
            return
        self._append_item(text)
        self._input.clear()

    def _append_item(self, text: str):
        """向列表追加一项（附带单行删除按钮）。"""
        entry = str(text or '').strip()
        if not entry:
            return

        item = QListWidgetItem(self._list)
        item.setData(Qt.ItemDataRole.UserRole, entry)

        row_widget = QWidget(self._list)
        row_widget.setObjectName('valueRow')
        row_widget.setMinimumHeight(38)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(8)

        label = QLabel(entry, row_widget)
        label.setObjectName('valueLabel')
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        delete_btn = QPushButton(self._delete_text, row_widget)
        delete_btn.setObjectName('deleteItemButton')
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.clicked.connect(lambda _checked=False, current=item: self._remove_item(current))

        row_layout.addWidget(label, 1, Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        item.setSizeHint(QSize(0, 38))
        self._list.setItemWidget(item, row_widget)

    def _remove_item(self, item: QListWidgetItem):
        """删除一项。"""
        row = self._list.row(item)
        if row >= 0:
            self._list.takeItem(row)

    def values(self) -> list[str]:
        """读取当前列表值。"""
        out: list[str] = []
        seen: set[str] = set()
        for index in range(self._list.count()):
            item = self._list.item(index)
            text = str(item.data(Qt.ItemDataRole.UserRole) or '').strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out


class FeaturePanel(QWidget):
    """承载 `FeaturePanel` 相关界面控件与交互逻辑。"""

    config_changed = pyqtSignal(object)
    _FORCED_OFF_ICON = (Path(__file__).resolve().parents[1] / 'icons' / 'disabled_x.svg').as_posix()
    _FORCED_OFF_STYLE = (
        'QCheckBox { color: #9ca3af; }'
        'QCheckBox::indicator {'
        '  width: 14px; height: 14px; border: 1.5px solid #d1d5db;'
        '  border-radius: 3px; background: #f3f4f6;'
        '}'
        'QCheckBox::indicator:unchecked:disabled {'
        f'  image: url({_FORCED_OFF_ICON});'
        '}'
        'QCheckBox::indicator:checked:disabled {'
        f'  image: url({_FORCED_OFF_ICON});'
        '}'
    )

    def __init__(self, config: AppConfig, parent=None):
        """初始化对象并准备运行所需状态。"""
        super().__init__(parent)
        self.config = config
        panel_labels = load_config_json_object('ui_labels.json', prefer_user=False).get('feature_panel', {})
        self._task_title_map = panel_labels.get('task_titles', {})
        self._feature_label_map = panel_labels.get('feature_labels', {})
        feature_hints = panel_labels.get('feature_hints', {})
        self._feature_hint_map = feature_hints if isinstance(feature_hints, dict) else {}
        self._enabled_text = str(panel_labels.get('enabled', 'Enable'))
        self._empty_text = str(panel_labels.get('empty_text', 'No configurable feature items'))
        self._task_title_suffix = str(panel_labels.get('task_title_suffix', ' task'))
        self._detail_text = str(panel_labels.get('detail_text', '详情'))
        self._list_empty_text = str(panel_labels.get('list_empty_text', '未配置'))
        self._list_count_text = str(panel_labels.get('list_count_text', '已配置 {count} 条'))
        self._list_dialog_title_suffix = str(panel_labels.get('list_dialog_title_suffix', '详情'))
        self._list_dialog_hint = str(panel_labels.get('list_dialog_hint', '在弹窗中维护列表项。'))
        self._list_add_text = str(panel_labels.get('list_add_text', '新增'))
        self._list_delete_text = str(panel_labels.get('list_delete_text', '删除'))
        self._list_save_text = str(panel_labels.get('list_save_text', '保存'))
        self._list_cancel_text = str(panel_labels.get('list_cancel_text', '取消'))
        self._list_input_placeholder = str(panel_labels.get('list_input_placeholder', '输入内容'))
        list_texts = panel_labels.get('list_texts', {})
        self._list_text_map = list_texts if isinstance(list_texts, dict) else {}
        self._loading = True
        self._feature_boxes: dict[tuple[str, str], QCheckBox] = {}
        self._list_feature_labels: dict[tuple[str, str], QLabel] = {}
        self._init_ui()
        self._load_config()
        self._connect_auto_save()
        self._loading = False

    def _init_ui(self):
        """初始化 `ui` 相关状态或界面。"""
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)
        idx = 0
        task_names = [str(name) for name in getattr(self.config, 'tasks', {}).keys()]
        for task_name in task_names:
            task_cfg = self.config.tasks.get(task_name)
            if task_cfg is None:
                continue
            feature_map = getattr(task_cfg, 'features', {}) or {}
            if not isinstance(feature_map, dict) or not feature_map:
                continue
            group = self._build_task_group(task_name, feature_map)
            grid.addWidget(group, idx // 2, idx % 2)
            idx += 1

        if idx == 0:
            empty = QLabel(self._empty_text)
            empty.setStyleSheet('color: #94a3b8;')
            root.addWidget(empty)
        else:
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            root.addLayout(grid)
        root.addStretch()

    def _build_task_group(self, task_name: str, feature_map: dict[str, Any]) -> QGroupBox:
        """构建 `task_group` 对应的结构或组件。"""
        title = self._task_title_map.get(task_name, f'{task_name}{self._task_title_suffix}')
        group = QGroupBox(title)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 4)
        form.setSpacing(10)
        for feature_name, feature_value in feature_map.items():
            label = self._feature_label_map.get(feature_name, feature_name)
            if isinstance(feature_value, list):
                form.addRow(f'{label}:', self._build_list_feature_row(task_name, feature_name))
                continue

            cb = QCheckBox(self._enabled_text)
            self._feature_boxes[(task_name, feature_name)] = cb
            hint_text = self._feature_hint_text(task_name, feature_name)
            if hint_text:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)
                row_layout.addWidget(cb)
                hint_label = QLabel(hint_text)
                hint_label.setWordWrap(True)
                hint_label.setStyleSheet('color: #dc2626; font-size: 12px;')
                row_layout.addWidget(hint_label, 1)
                form.addRow(f'{label}:', row_widget)
            else:
                form.addRow(f'{label}:', cb)
        group.setLayout(form)
        return group

    def _build_list_feature_row(self, task_name: str, feature_name: str) -> QWidget:
        """构建列表型功能项行（主界面仅显示摘要，不显示具体昵称）。"""
        row_widget = QWidget(self)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        summary = QLabel(
            self._resolve_list_text(task_name, feature_name, 'list_empty_text', self._list_empty_text), row_widget
        )
        summary.setStyleSheet('color: #64748b;')
        self._list_feature_labels[(task_name, feature_name)] = summary

        detail_btn = QPushButton(self._detail_text, row_widget)
        detail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        detail_btn.setMinimumHeight(26)
        detail_btn.setStyleSheet(
            """
            QPushButton {
                min-width: 0px;
                min-height: 26px;
                border-radius: 6px;
                background: #f1f5f9;
                color: #334155;
                border: 1px solid #e2e8f0;
                font-weight: 600;
                font-size: 11px;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: #e2e8f0;
                border-color: #cbd5e1;
            }
            """
        )
        detail_btn.clicked.connect(
            lambda _checked=False, name=task_name, feature=feature_name: self._open_list_feature_editor(name, feature)
        )

        row.addWidget(summary, 1)
        row.addWidget(detail_btn)
        return row_widget

    def _resolve_list_text(self, task_name: str, feature_name: str, key: str, default: str) -> str:
        """读取列表型文案，优先 task.feature 级别，其次 feature 级别，最后全局默认。"""
        full_key = f'{task_name}.{feature_name}'
        full_cfg = self._list_text_map.get(full_key, {})
        if isinstance(full_cfg, dict) and key in full_cfg:
            text = str(full_cfg.get(key) or '').strip()
            if text:
                return text

        feature_cfg = self._list_text_map.get(feature_name, {})
        if isinstance(feature_cfg, dict) and key in feature_cfg:
            text = str(feature_cfg.get(key) or '').strip()
            if text:
                return text

        return str(default or '').strip()

    def _feature_hint_text(self, task_name: str, feature_name: str) -> str:
        """读取功能项提示文本，优先 task.feature 级别。"""
        full_key = f'{task_name}.{feature_name}'
        text = self._feature_hint_map.get(full_key, self._feature_hint_map.get(feature_name, ''))
        return str(text or '').strip()

    def _connect_auto_save(self):
        """绑定 `auto_save` 相关信号或回调。"""
        for cb in self._feature_boxes.values():
            cb.toggled.connect(self._auto_save)

    def _auto_save(self):
        """执行 `auto save` 相关处理。"""
        if self._loading:
            return
        c = self.config
        for (task_name, feature_name), cb in self._feature_boxes.items():
            task_cfg = c.tasks.get(task_name)
            if task_cfg is None:
                continue
            feature_map = dict(getattr(task_cfg, 'features', {}) or {})
            if is_feature_forced_off(task_name, feature_name):
                feature_map[str(feature_name)] = False
            else:
                feature_map[str(feature_name)] = bool(cb.isChecked())
            task_cfg.features = feature_map
        c.save()
        self.config_changed.emit(c)

    @staticmethod
    def _normalize_feature_list(value: Any) -> list[str]:
        """规范化列表型功能项配置。"""
        if not isinstance(value, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for raw in value:
            text = str(raw or '').strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    def _read_list_feature(self, task_name: str, feature_name: str) -> list[str]:
        """读取并规范化列表型配置值。"""
        task_cfg = self.config.tasks.get(task_name)
        if task_cfg is None:
            return []
        feature_map = getattr(task_cfg, 'features', {}) or {}
        if not isinstance(feature_map, dict):
            return []
        return self._normalize_feature_list(feature_map.get(feature_name, []))

    def _set_list_feature(self, task_name: str, feature_name: str, values: list[str]) -> bool:
        """写入列表型配置并持久化。"""
        task_cfg = self.config.tasks.get(task_name)
        if task_cfg is None:
            return False
        feature_map = dict(getattr(task_cfg, 'features', {}) or {})
        feature_map[str(feature_name)] = self._normalize_feature_list(values)
        task_cfg.features = feature_map
        self.config.save()
        self.config_changed.emit(self.config)
        self._refresh_list_feature_summary(task_name, feature_name)
        return True

    def _refresh_list_feature_summary(self, task_name: str, feature_name: str):
        """刷新列表型功能项摘要文案。"""
        label = self._list_feature_labels.get((task_name, feature_name))
        if label is None:
            return
        empty_text = self._resolve_list_text(task_name, feature_name, 'list_empty_text', self._list_empty_text)
        count_text = self._resolve_list_text(task_name, feature_name, 'list_count_text', self._list_count_text)
        count = len(self._read_list_feature(task_name, feature_name))
        if count <= 0:
            label.setText(empty_text)
            return
        label.setText(count_text.format(count=count))

    def _open_list_feature_editor(self, task_name: str, feature_name: str):
        """打开列表型功能项编辑弹窗。"""
        feature_label = self._feature_label_map.get(feature_name, feature_name)
        task_title = self._task_title_map.get(task_name, f'{task_name}{self._task_title_suffix}')
        dialog = ListFeatureEditorDialog(
            title=f'{task_title} - {feature_label}{self._list_dialog_title_suffix}',
            values=self._read_list_feature(task_name, feature_name),
            add_text=self._list_add_text,
            delete_text=self._list_delete_text,
            save_text=self._list_save_text,
            cancel_text=self._list_cancel_text,
            input_placeholder=self._resolve_list_text(
                task_name, feature_name, 'list_input_placeholder', self._list_input_placeholder
            ),
            hint_text=self._resolve_list_text(task_name, feature_name, 'list_dialog_hint', self._list_dialog_hint),
            parent=self,
        )
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return
        self._set_list_feature(task_name, feature_name, dialog.values())

    def _load_config(self):
        """加载 `config` 相关数据。"""
        c = self.config
        for (task_name, feature_name), cb in self._feature_boxes.items():
            task_cfg = c.tasks.get(task_name)
            if task_cfg is None:
                continue
            feature_map = getattr(task_cfg, 'features', {}) or {}
            forced = is_feature_forced_off(task_name, feature_name)
            if forced:
                cb.setChecked(False)
                cb.setEnabled(False)
                cb.setToolTip('该功能为固定禁用项')
                cb.setStyleSheet(self._FORCED_OFF_STYLE)
            else:
                cb.setEnabled(True)
                cb.setToolTip('')
                cb.setStyleSheet('')
                cb.setChecked(bool(feature_map.get(feature_name, False)))

        for task_name, feature_name in self._list_feature_labels.keys():
            self._refresh_list_feature_summary(task_name, feature_name)

    def set_config(self, config: AppConfig):
        """替换配置对象并刷新界面。"""
        self.config = config
        self._loading = True
        self._load_config()
        self._loading = False
