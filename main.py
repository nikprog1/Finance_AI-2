"""
Bank Statement Analyzer MVP — главное окно PyQt5.
Вкладки: Транзакции (таблица с редактированием категории), Графики (круговая и столбчатая).
"""
import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QToolBar,
    QFileDialog,
    QComboBox,
    QStyledItemDelegate,
    QAbstractItemView,
    QScrollArea,
    QLabel,
    QFrame,
)
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import database as db
import csv_import
import financial_agent

CATEGORIES = ["Продукты", "Транспорт", "Развлечения", "Кафе", "Без категории"]


class CategoryDelegate(QStyledItemDelegate):
    """Делегат: при редактировании ячейки «Категория» показывается QComboBox с фиксированным списком."""

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItems(CATEGORIES)
        return editor

    def setEditorData(self, editor: QComboBox, index):
        value = index.model().data(index, Qt.EditRole)
        i = editor.findText(value if value else "Без категории")
        editor.setCurrentIndex(max(0, i))

    def setModelData(self, editor: QComboBox, model, index):
        category = editor.currentText()
        model.setData(index, category, Qt.EditRole)
        # id хранится в UserRole в колонке 0 той же строки
        row = index.row()
        id_index = model.index(row, 0)
        row_id = model.data(id_index, Qt.UserRole)
        if row_id is not None:
            conn = getattr(self, "_conn", None)
            if conn:
                db.update_category(conn, int(row_id), category)


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self._conn = conn
        self.setWindowTitle("Bank Statement Analyzer MVP")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

        # Тулбар
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        load_act = toolbar.addAction("Загрузить CSV")
        load_act.triggered.connect(self._on_load_csv)
        dedup_act = toolbar.addAction("Удалить дубликаты")
        dedup_act.triggered.connect(self._on_remove_duplicates)
        charts_act = toolbar.addAction("Графики")
        charts_act.triggered.connect(self._on_show_charts)

        # Статус-бар
        self.statusBar().showMessage("Готово")

        # Вкладки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Вкладка «Транзакции» — таблица слева, панель рекомендаций справа
        self.table_tab = QWidget()
        table_and_panel = QHBoxLayout(self.table_tab)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Дата", "Номер карты", "Описание", "Сумма", "Категория"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setItemDelegateForColumn(4, CategoryDelegate(self))
        self.table_tab._delegate = self.table.itemDelegateForColumn(4)
        self.table_tab._delegate._conn = conn
        table_and_panel.addWidget(self.table, 1)

        # Панель рекомендаций (справа, ~300 px)
        self.recommendations_panel = QFrame()
        self.recommendations_panel.setMinimumWidth(300)
        self.recommendations_panel.setMaximumWidth(320)
        self.recommendations_panel.setFrameShape(QFrame.StyledPanel)
        rec_layout = QVBoxLayout(self.recommendations_panel)
        rec_title = QLabel("Финансовые советы")
        rec_title.setFont(QFont(rec_title.font().family(), 10, QFont.Bold))
        rec_layout.addWidget(rec_title)
        self.recommendations_scroll = QScrollArea()
        self.recommendations_scroll.setWidgetResizable(True)
        self.recommendations_content = QWidget()
        self.recommendations_content_layout = QVBoxLayout(self.recommendations_content)
        self.recommendations_content_layout.setAlignment(Qt.AlignTop)
        self.recommendations_scroll.setWidget(self.recommendations_content)
        self.recommendations_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rec_layout.addWidget(self.recommendations_scroll, 1)
        table_and_panel.addWidget(self.recommendations_panel)

        self.tabs.addTab(self.table_tab, "Транзакции")

        # Вкладка «Графики» — один холст с двумя subplot
        self.charts_tab = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_tab)
        self.fig = Figure(figsize=(6, 8))
        self.chart_canvas = FigureCanvasQTAgg(self.fig)
        self.charts_layout.addWidget(self.chart_canvas)
        self.tabs.addTab(self.charts_tab, "Графики")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # При запуске удаляем дубликаты (дата + описание + сумма), затем загружаем таблицу и рекомендации
        db.remove_duplicates(self._conn)
        self._reload_table()
        self._refresh_recommendations()
        self._refresh_charts()

    def _reload_table(self):
        """Заполнить таблицу из БД. В колонке 0 в UserRole хранится id."""
        self.model.removeRows(0, self.model.rowCount())
        for row in db.get_all_transactions(self._conn):
            id_item = QStandardItem(row["date"])
            id_item.setData(row["id"], Qt.UserRole)
            id_item.setEditable(False)
            card = (row.get("card_number") or "").strip()
            self.model.appendRow([
                id_item,
                QStandardItem(card),
                QStandardItem(row["description"]),
                QStandardItem(str(row["amount"])),
                QStandardItem(row["category"] or "Без категории"),
            ])
        # Только колонка «Категория» (индекс 4) редактируемая
        for r in range(self.model.rowCount()):
            for c in (0, 1, 2, 3):
                it = self.model.item(r, c)
                if it:
                    it.setEditable(False)
        self._refresh_recommendations()

    def _refresh_recommendations(self):
        """Обновить панель рекомендаций AI-агента."""
        # Очистить текущее содержимое
        while self.recommendations_content_layout.count():
            child = self.recommendations_content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        recs = financial_agent.get_recommendations(self._conn)
        if not recs:
            hint = QLabel("Недостаточно данных для анализа.\nЗагрузите CSV с транзакциями.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color: gray;")
            self.recommendations_content_layout.addWidget(hint)
        else:
            for rec in recs:
                text_label = QLabel(rec.text)
                text_label.setWordWrap(True)
                text_label.setFont(QFont(text_label.font().family(), 9, QFont.Bold))
                self.recommendations_content_layout.addWidget(text_label)
                why_label = QLabel("Почему это важно?\n" + rec.why)
                why_label.setWordWrap(True)
                why_label.setStyleSheet("color: gray; font-size: 11px;")
                self.recommendations_content_layout.addWidget(why_label)
                self.recommendations_content_layout.addSpacing(12)

    def _on_remove_duplicates(self):
        """Удалить дубликаты транзакций (по дате, описанию, сумме, номеру карты), обновить таблицу и рекомендации."""
        deleted = db.remove_duplicates(self._conn)
        self._reload_table()
        self._refresh_charts()
        self.statusBar().showMessage(f"Удалено дубликатов: {deleted}")

    def _on_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите CSV выписку Тинькофф",
            "",
            "CSV (*.csv);;Все файлы (*)",
        )
        if not path:
            return
        try:
            n = csv_import.import_from_csv(self._conn, path)
            self._reload_table()  # также обновляет рекомендации
            self.statusBar().showMessage(f"Загружено записей: {n}")
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка: {e}")

    def _on_show_charts(self):
        self.tabs.setCurrentWidget(self.charts_tab)
        self._refresh_charts()

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) == self.charts_tab:
            self._refresh_charts()

    def _refresh_charts(self):
        """Обновить круговую и столбчатую диаграммы по данным из БД."""
        self.fig.clear()
        # Круговая — расходы по категориям за последние 30 дней
        data_pie = db.get_expenses_by_category_last_month(self._conn)
        ax1 = self.fig.add_subplot(2, 1, 1)
        if data_pie:
            categories_pie, amounts_pie = zip(*data_pie)
            ax1.pie(amounts_pie, labels=categories_pie, autopct="%1.1f%%")
            ax1.set_title("Расходы по категориям (последние 30 дней)")
        else:
            ax1.text(0.5, 0.5, "Нет данных за последние 30 дней", ha="center", va="center")
        # Столбчатая — по дням за последние 7 дней
        data_bar = db.get_expenses_by_day_last_week(self._conn)
        ax2 = self.fig.add_subplot(2, 1, 2)
        if data_bar:
            days, amounts_bar = zip(*data_bar)
            ax2.bar(range(len(days)), amounts_bar, tick_label=list(days))
            ax2.set_title("Расходы по дням (последние 7 дней)")
            ax2.tick_params(axis="x", rotation=45)
        else:
            ax2.text(0.5, 0.5, "Нет данных за последние 7 дней", ha="center", va="center")
        self.fig.tight_layout()
        self.chart_canvas.draw()


def main():
    app = QApplication([])
    conn = db.get_connection()
    db.init_db(conn)
    win = MainWindow(conn)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
