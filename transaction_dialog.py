"""
Диалог добавления/редактирования транзакции.
"""
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QFormLayout,
)
from PyQt5.QtCore import QDate
from PyQt5.QtGui import QFont

import database as db

CATEGORIES = ["Продукты", "Транспорт", "Развлечения", "Кафе", "Без категории", "Супермаркеты", "Фастфуд", "Цифровые товары", "Мобильная связь"]


class TransactionEditDialog(QDialog):
    def __init__(self, parent=None, conn=None, mode="add", row_data=None):
        super().__init__(parent)
        self._conn = conn
        self._mode = mode
        self._row_data = row_data or {}
        self.setWindowTitle("Добавить транзакцию" if mode == "add" else "Редактировать транзакцию")
        self.setMinimumWidth(400)
        layout = QFormLayout()
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("ГГГГ-ММ-ДД или ДД.ММ.ГГГГ")
        layout.addRow("Дата:", self.date_edit)
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Описание")
        layout.addRow("Описание:", self.desc_edit)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(-1e9, 1e9)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(0)
        layout.addRow("Сумма (₽, + доход, − расход):", self.amount_spin)
        self.category_combo = QComboBox()
        self.category_combo.addItems(CATEGORIES)
        layout.addRow("Категория:", self.category_combo)
        self.card_edit = QLineEdit()
        self.card_edit.setPlaceholderText("Номер карты (опц.)")
        layout.addRow("Номер карты:", self.card_edit)
        if mode == "edit" and row_data:
            self.date_edit.setText(str(row_data.get("date", ""))[:10])
            self.desc_edit.setText(str(row_data.get("description", "")))
            self.amount_spin.setValue(float(row_data.get("amount", 0)))
            cat = row_data.get("category") or "Без категории"
            i = self.category_combo.findText(cat)
            self.category_combo.setCurrentIndex(max(0, i))
            self.card_edit.setText(str(row_data.get("card_number", "") or ""))
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save)
        btns.addWidget(save_btn)
        layout.addRow(btns)
        self.setLayout(layout)

    def _parse_date(self, s):
        from datetime import datetime
        s = s.strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
            try:
                dt = datetime.strptime(s[:19], fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None

    def _save(self):
        date_str = self._parse_date(self.date_edit.text())
        if not date_str:
            self.date_edit.setFocus()
            return
        desc = self.desc_edit.text().strip() or "—"
        amount = self.amount_spin.value()
        cat = self.category_combo.currentText() or "Без категории"
        card = self.card_edit.text().strip() or ""
        if self._mode == "add":
            db.insert_transaction(self._conn, date_str, desc, amount, cat, card)
        else:
            row_id = self._row_data.get("id")
            if row_id:
                db.update_transaction(
                    self._conn, int(row_id),
                    date=date_str, description=desc, amount=amount,
                    category=cat, card_number=card or None,
                )
        self.accept()
