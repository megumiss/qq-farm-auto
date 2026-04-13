"""统一弹窗样式。"""

UNIFIED_DIALOG_STYLE = """
QDialog, QMessageBox, QInputDialog {
    background-color: #f8fafc;
}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #334155;
    font-size: 13px;
}
QDialog QLineEdit, QInputDialog QLineEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 8px;
    color: #0f172a;
    min-width: 220px;
}
QDialog QLineEdit:focus, QInputDialog QLineEdit:focus {
    border-color: #2563eb;
}
QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    min-width: 84px;
    min-height: 30px;
    border-radius: 8px;
    border: 1px solid #dbe3ef;
    background: #f8fafc;
    color: #334155;
    font-weight: 600;
    padding: 2px 10px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {
    background: #eef2ff;
    border-color: #c7d2fe;
}
"""
