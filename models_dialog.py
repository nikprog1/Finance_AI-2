"""
Управление моделями ИИ (порт из ChatList).
Работает с database через conn.
"""
import sqlite3
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

import database as db


class ModelEditDialog(QDialog):
    def __init__(self, parent=None, conn: Optional[sqlite3.Connection] = None, model_data=None):
        super().__init__(parent)
        self._conn = conn
        self._model_data = model_data
        self.setWindowTitle("Редактировать модель" if model_data else "Добавить модель")
        self.setMinimumWidth(450)
        layout = QVBoxLayout()
        fl = QHBoxLayout()
        fl.addWidget(QLabel("Название:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: GPT-4")
        fl.addWidget(self.name_input)
        layout.addLayout(fl)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("API URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://openrouter.ai/api/v1/chat/completions")
        fl.addWidget(self.url_input)
        layout.addLayout(fl)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("API ID (env):"))
        self.api_id_input = QLineEdit()
        self.api_id_input.setPlaceholderText("OPENROUTER_API_KEY")
        fl.addWidget(self.api_id_input)
        layout.addLayout(fl)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("API ключ:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Опционально")
        fl.addWidget(self.api_key_input)
        layout.addLayout(fl)
        fl = QHBoxLayout()
        fl.addWidget(QLabel("Тип:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "openrouter", "deepseek", "groq", "custom"])
        fl.addWidget(self.provider_combo)
        layout.addLayout(fl)
        self.active_check = QCheckBox("Модель активна")
        self.active_check.setChecked(True)
        layout.addWidget(self.active_check)
        if model_data:
            self.name_input.setText(model_data.get("name", ""))
            self.url_input.setText(model_data.get("api_url", ""))
            self.api_id_input.setText(model_data.get("api_id", ""))
            self.api_key_input.setText(model_data.get("api_key") or "")
            i = self.provider_combo.findText(model_data.get("provider_type", "custom"))
            self.provider_combo.setCurrentIndex(max(0, i))
            self.active_check.setChecked(model_data.get("is_active", 1) == 1)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save)
        btns.addWidget(save_btn)
        layout.addLayout(btns)
        self.setLayout(layout)

    def _save(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        api_id = self.api_id_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название модели")
            return
        if not url or not url.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Ошибка", "Введите корректный API URL")
            return
        if not api_id:
            QMessageBox.warning(self, "Ошибка", "Введите API ID (переменную окружения)")
            return
        api_key = self.api_key_input.text().strip() or None
        provider = self.provider_combo.currentText()
        is_active = 1 if self.active_check.isChecked() else 0
        try:
            if self._model_data:
                db.update_model(
                    self._conn,
                    self._model_data["id"],
                    name=name, api_url=url, api_id=api_id,
                    api_key=api_key, provider_type=provider, is_active=is_active,
                )
            else:
                db.add_model(
                    self._conn, name, url, api_id,
                    provider_type=provider, is_active=is_active, api_key=api_key,
                )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
            return
        QMessageBox.information(self, "Успех", "Модель сохранена")
        self.accept()


class ModelsManagementWidget(QWidget):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self._conn = conn
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Управление моделями"))
        btns = QHBoxLayout()
        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(self._add)
        btns.addWidget(add_btn)
        edit_btn = QPushButton("Редактировать")
        edit_btn.clicked.connect(self._edit)
        btns.addWidget(edit_btn)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._load)
        btns.addWidget(refresh_btn)
        btns.addStretch()
        layout.addLayout(btns)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "API URL", "API ID", "Тип", "Активна"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self._load()

    def _load(self):
        models = db.get_all_models(self._conn)
        self.table.setRowCount(len(models))
        for i, m in enumerate(models):
            self.table.setItem(i, 0, QTableWidgetItem(str(m.get("id", ""))))
            self.table.item(i, 0).setData(Qt.UserRole, m.get("id"))
            self.table.setItem(i, 1, QTableWidgetItem(str(m.get("name", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(str(m.get("api_url", ""))))
            self.table.setItem(i, 3, QTableWidgetItem(str(m.get("api_id", ""))))
            self.table.setItem(i, 4, QTableWidgetItem(str(m.get("provider_type", ""))))
            self.table.setItem(i, 5, QTableWidgetItem("Да" if m.get("is_active") == 1 else "Нет"))

    def _add(self):
        dlg = ModelEditDialog(self, conn=self._conn)
        if dlg.exec_() == dlg.Accepted:
            self._load()

    def _edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Подсказка", "Выберите модель")
            return
        mid = self.table.item(row, 0).data(Qt.UserRole)
        models = db.get_all_models(self._conn)
        model_data = next((m for m in models if m.get("id") == mid), None)
        if not model_data:
            return
        dlg = ModelEditDialog(self, conn=self._conn, model_data=model_data)
        if dlg.exec_() == dlg.Accepted:
            self._load()

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        mid = self.table.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(
            self, "Подтверждение", "Удалить модель?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        if db.delete_model(self._conn, mid):
            self._load()
