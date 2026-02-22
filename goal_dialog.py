"""
Диалог добавления/редактирования финансовой цели.
"""
from datetime import date, datetime

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QDateEdit,
    QPushButton,
    QHBoxLayout,
)
from PyQt5.QtCore import QDate

import database as db


def calc_monthly_savings(target: float, end_date: str, current: float) -> float:
    try:
        end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0.0
    today = date.today()
    if end <= today:
        return 0.0
    months = max(1, (end.year - today.year) * 12 + (end.month - today.month))
    remaining = max(0.0, float(target) - float(current))
    return round(remaining / months, 2)


class GoalEditDialog(QDialog):
    def __init__(self, parent=None, conn=None, mode="add", goal_data=None):
        super().__init__(parent)
        self._conn = conn
        self._mode = mode
        self._goal_data = goal_data or {}
        self.setWindowTitle("Добавить цель" if mode == "add" else "Редактировать цель")
        self.setMinimumWidth(400)
        layout = QFormLayout()
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Описание цели")
        layout.addRow("Описание:", self.desc_edit)
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setMinimum(0)
        self.amount_spin.setMaximum(1e12)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setValue(100000)
        layout.addRow("Целевая сумма (₽):", self.amount_spin)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        layout.addRow("Дата начала:", self.start_date)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setMinimumDate(QDate.currentDate().addMonths(1))
        self.end_date.setDate(QDate.currentDate().addMonths(12))
        layout.addRow("Дата окончания:", self.end_date)
        self.progress_spin = QDoubleSpinBox()
        self.progress_spin.setMinimum(0)
        self.progress_spin.setMaximum(1e12)
        self.progress_spin.setValue(0)
        layout.addRow("Текущий прогресс (₽):", self.progress_spin)
        if mode == "edit" and goal_data:
            self.desc_edit.setText(goal_data.get("description", ""))
            self.amount_spin.setValue(float(goal_data.get("target_amount", 0)))
            sd = goal_data.get("start_date", "")
            if sd:
                try:
                    d = datetime.strptime(sd[:10], "%Y-%m-%d")
                    self.start_date.setDate(QDate(d.year, d.month, d.day))
                except ValueError:
                    pass
            ed = goal_data.get("end_date", "")
            if ed:
                try:
                    d = datetime.strptime(ed[:10], "%Y-%m-%d")
                    self.end_date.setDate(QDate(d.year, d.month, d.day))
                except ValueError:
                    pass
            self.progress_spin.setValue(float(goal_data.get("current_progress", 0)))
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

    def _save(self):
        desc = self.desc_edit.text().strip()
        if not desc:
            self.desc_edit.setFocus()
            return
        target = self.amount_spin.value()
        start_str = self.start_date.date().toString("yyyy-MM-dd")
        end_str = self.end_date.date().toString("yyyy-MM-dd")
        progress = self.progress_spin.value()
        if self._mode == "add":
            db.create_goal(self._conn, desc, target, start_str, end_str, progress)
        else:
            gid = self._goal_data.get("id")
            if gid:
                db.update_goal(
                    self._conn, int(gid),
                    description=desc, target_amount=target,
                    start_date=start_str, end_date=end_str,
                    current_progress=progress,
                )
        self.accept()
