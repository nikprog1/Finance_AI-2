"""
Bank Statement Analyzer MVP — главное окно PyQt5.
Вкладки: Транзакции (таблица с редактированием категории), Графики (круговая и столбчатая).
"""
import logging
import sqlite3

from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QObject

from env_loader import load_env
from logging_config import setup_logging
from version import __version__

logger = logging.getLogger(__name__)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QDoubleSpinBox,
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
    QPushButton,
    QLineEdit,
    QMessageBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
)
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import database as db
import csv_import
import financial_agent
from models_dialog import ModelsManagementWidget

CATEGORIES = ["Продукты", "Транспорт", "Развлечения", "Кафе", "Без категории"]


class GoalWorker(QObject):
    """Воркер для вызова облачного ИИ (выполняется в фоне, БД не трогаем)."""
    finished = pyqtSignal(object)  # tuple[str, bool]: (текст, from_ai)

    def __init__(self):
        super().__init__()
        self.metrics = None
        self.rule_text = ""
        self.consent = False
        self.api_config = None  # опционально: url, key, model, timeout из БД

    def do_work(self):
        if not self.consent:
            self.finished.emit((self.rule_text, False))
            return
        try:
            from llm_agent import get_agent
            agent = get_agent()
            result = agent.generate_expense_advice(self.metrics, api_config=self.api_config)
            if result:
                self.finished.emit((result, True))
            else:
                self.finished.emit((self.rule_text, False))
        except Exception as e:
            logger.exception("Goal worker: %s", e)
            self.finished.emit((self.rule_text, False))


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


class MainWindow(QMainWindow):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self._conn = conn
        self.setWindowTitle(f"Bank Statement Analyzer MVP v{__version__}")
        self.setMinimumSize(800, 600)
        self.resize(900, 650)

        # Тулбар
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        load_act = toolbar.addAction("Загрузить CSV")
        load_act.triggered.connect(self._on_load_csv)
        charts_act = toolbar.addAction("Графики")
        charts_act.triggered.connect(self._on_show_charts)

        # Статус-бар
        self.statusBar().showMessage("Готово")

        # Вкладки
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Вкладка «Транзакции» — поиск/фильтры, таблица слева, панель рекомендаций справа
        self.table_tab = QWidget()
        table_main = QVBoxLayout(self.table_tab)
        # Панель поиска и фильтров
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск (дата, категория, сумма, описание, карта)")
        self.search_edit.setMinimumWidth(200)
        filter_row.addWidget(QLabel("Поиск:"))
        filter_row.addWidget(self.search_edit)
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDate(QDate.currentDate().addYears(-1))
        filter_row.addWidget(QLabel("С:"))
        filter_row.addWidget(self.date_from_edit)
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDate(QDate.currentDate())
        filter_row.addWidget(QLabel("По:"))
        filter_row.addWidget(self.date_to_edit)
        self.category_filter = QComboBox()
        self.category_filter.addItem("— Все категории —", None)
        filter_row.addWidget(QLabel("Категория:"))
        filter_row.addWidget(self.category_filter)
        self.card_filter = QComboBox()
        self.card_filter.addItem("— Все карты —", None)
        filter_row.addWidget(QLabel("Карта:"))
        filter_row.addWidget(self.card_filter)
        self.op_type_filter = QComboBox()
        self.op_type_filter.addItem("Все", "all")
        self.op_type_filter.addItem("Доходы", "income")
        self.op_type_filter.addItem("Расходы", "expense")
        filter_row.addWidget(QLabel("Тип:"))
        filter_row.addWidget(self.op_type_filter)
        search_btn = QPushButton("Поиск")
        search_btn.clicked.connect(self._on_search)
        filter_row.addWidget(search_btn)
        edit_btn = QPushButton("Редактировать")
        edit_btn.clicked.connect(self._on_edit_transaction_focus)
        filter_row.addWidget(edit_btn)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._on_delete_transaction)
        filter_row.addWidget(del_btn)
        filter_row.addStretch()
        table_main.addLayout(filter_row)
        table_and_panel = QHBoxLayout()
        table_main.addLayout(table_and_panel)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Дата", "Номер карты", "Описание", "Сумма", "Категория"])
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.setItemDelegateForColumn(4, CategoryDelegate(self))
        self.model.dataChanged.connect(self._on_transaction_data_changed)
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
        self.advice_consent_check = QCheckBox("Разрешить анализ через защищённый облачный ИИ")
        rec_layout.addWidget(self.advice_consent_check)
        self.advice_request_btn = QPushButton("Получить рекомендации")
        self.advice_request_btn.clicked.connect(self._on_advice_request)
        rec_layout.addWidget(self.advice_request_btn)
        table_and_panel.addWidget(self.recommendations_panel)

        # Поток для вызова облачного ИИ по цели
        self._goal_thread = QThread()
        self._goal_worker = GoalWorker()
        self._goal_worker.moveToThread(self._goal_thread)
        self._goal_thread.started.connect(self._goal_worker.do_work)
        self._goal_worker.finished.connect(self._on_goal_finished)

        self.tabs.addTab(self.table_tab, "Транзакции")

        # Вкладка «Финансовые цели»
        self.goals_tab = QWidget()
        goals_layout = QVBoxLayout(self.goals_tab)
        goals_title = QLabel("Финансовые цели")
        goals_title.setFont(QFont(goals_title.font().family(), 12, QFont.Bold))
        goals_layout.addWidget(goals_title)
        goals_btns = QHBoxLayout()
        goals_add_btn = QPushButton("Добавить")
        goals_add_btn.clicked.connect(self._on_add_goal)
        goals_btns.addWidget(goals_add_btn)
        goals_edit_btn = QPushButton("Редактировать")
        goals_edit_btn.clicked.connect(self._on_edit_goal)
        goals_btns.addWidget(goals_edit_btn)
        goals_del_btn = QPushButton("Удалить")
        goals_del_btn.clicked.connect(self._on_delete_goal)
        goals_btns.addWidget(goals_del_btn)
        goals_btns.addStretch()
        goals_layout.addLayout(goals_btns)
        self.goals_table = QTableWidget()
        self.goals_table.setColumnCount(7)
        self.goals_table.setHorizontalHeaderLabels([
            "Описание", "Целевая сумма", "Начало", "Конец", "Прогресс", "Рег. сумма/мес", "Прогресс %"
        ])
        self.goals_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        goals_layout.addWidget(self.goals_table)
        self.tabs.addTab(self.goals_tab, "Финансовые цели")

        # Вкладка «Общее»
        self.overview_tab = QWidget()
        overview_layout = QVBoxLayout(self.overview_tab)
        overview_title = QLabel("Обзор доходов и расходов")
        overview_title.setFont(QFont(overview_title.font().family(), 12, QFont.Bold))
        overview_layout.addWidget(overview_title)
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Период:"))
        self.overview_year_combo = QComboBox()
        from datetime import date
        year = date.today().year
        for y in range(year, year - 6, -1):
            self.overview_year_combo.addItem(str(y), y)
        self.overview_year_combo.addItem("Произвольный", None)
        period_row.addWidget(self.overview_year_combo)
        self.overview_date_from = QDateEdit()
        self.overview_date_from.setCalendarPopup(True)
        self.overview_date_from.setDate(QDate(year, 1, 1))
        period_row.addWidget(QLabel("С:"))
        period_row.addWidget(self.overview_date_from)
        self.overview_date_to = QDateEdit()
        self.overview_date_to.setCalendarPopup(True)
        self.overview_date_to.setDate(QDate.currentDate())
        period_row.addWidget(QLabel("По:"))
        period_row.addWidget(self.overview_date_to)
        overview_refresh_btn = QPushButton("Обновить")
        overview_refresh_btn.clicked.connect(self._load_overview)
        period_row.addWidget(overview_refresh_btn)
        period_row.addStretch()
        overview_layout.addLayout(period_row)
        self.overview_scroll = QScrollArea()
        self.overview_scroll.setWidgetResizable(True)
        self.overview_content = QWidget()
        self.overview_content_layout = QVBoxLayout(self.overview_content)
        self.overview_scroll.setWidget(self.overview_content)
        overview_layout.addWidget(self.overview_scroll)
        self.tabs.addTab(self.overview_tab, "Общее")

        # Вкладка «Настройки»
        self.settings_tab = QWidget()
        settings_layout = QVBoxLayout(self.settings_tab)
        settings_title = QLabel("Настройки программы")
        settings_title.setFont(QFont(settings_title.font().family(), 12, QFont.Bold))
        settings_layout.addWidget(settings_title)
        self.models_widget = ModelsManagementWidget(conn)
        settings_layout.addWidget(self.models_widget)
        settings_sep = QLabel("─" * 60)
        settings_layout.addWidget(settings_sep)
        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Таймаут запросов (сек):"))
        self.settings_timeout = QLineEdit()
        self.settings_timeout.setText(str(db.get_setting(conn, "request_timeout") or "30"))
        timeout_row.addWidget(self.settings_timeout)
        timeout_btn = QPushButton("Сохранить")
        timeout_btn.clicked.connect(lambda: self._save_setting("request_timeout", self.settings_timeout.text()))
        timeout_row.addWidget(timeout_btn)
        settings_layout.addLayout(timeout_row)
        tokens_row = QHBoxLayout()
        tokens_row.addWidget(QLabel("Макс. токенов:"))
        self.settings_tokens = QLineEdit()
        self.settings_tokens.setText(str(db.get_setting(conn, "max_tokens") or "2048"))
        tokens_row.addWidget(self.settings_tokens)
        tokens_btn = QPushButton("Сохранить")
        tokens_btn.clicked.connect(lambda: self._save_setting("max_tokens", self.settings_tokens.text() or "2048"))
        tokens_row.addWidget(tokens_btn)
        settings_layout.addLayout(tokens_row)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Тема:"))
        self.settings_theme = QComboBox()
        self.settings_theme.addItem("Светлая", "light")
        self.settings_theme.addItem("Тёмная", "dark")
        saved_theme = db.get_setting(conn, "ui_theme") or "light"
        idx = self.settings_theme.findData(saved_theme)
        if idx >= 0:
            self.settings_theme.setCurrentIndex(idx)
        self.settings_theme.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.settings_theme)
        theme_row.addStretch()
        settings_layout.addLayout(theme_row)
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Размер шрифта:"))
        self.settings_font = QComboBox()
        for s in ("8", "9", "10", "11", "12", "14", "16", "18", "20"):
            self.settings_font.addItem(f"{s} pt", s)
        saved_font = db.get_setting(conn, "font_size") or "10"
        fi = self.settings_font.findData(saved_font)
        if fi >= 0:
            self.settings_font.setCurrentIndex(fi)
        self.settings_font.currentIndexChanged.connect(self._on_font_changed)
        font_row.addWidget(self.settings_font)
        font_row.addStretch()
        settings_layout.addLayout(font_row)
        dedup_btn = QPushButton("Удалить дубликаты транзакций")
        dedup_btn.clicked.connect(self._on_dedup)
        settings_layout.addWidget(dedup_btn)
        settings_layout.addStretch()
        self.tabs.addTab(self.settings_tab, "Настройки")

        # Вкладка «Графики» — один холст с двумя subplot
        self.charts_tab = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_tab)
        self.fig = Figure(figsize=(6, 8))
        self.chart_canvas = FigureCanvasQTAgg(self.fig)
        self.charts_layout.addWidget(self.chart_canvas)
        self.tabs.addTab(self.charts_tab, "Графики")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._last_goal_result = None  # (text, from_ai) для отображения в «Финансовые советы»

        db.remove_duplicates(self._conn)
        self._refresh_filter_combos()
        self._reload_table()
        self._refresh_recommendations()
        self._refresh_charts()
        theme = db.get_setting(conn, "ui_theme") or "light"
        self._apply_theme(theme)
        font_size = db.get_setting(conn, "font_size") or "10"
        self._apply_font_size(int(font_size))

    def _get_search_filters(self):
        """Собрать фильтры для поиска."""
        date_from = self.date_from_edit.date().toString("yyyy-MM-dd")
        date_to = self.date_to_edit.date().toString("yyyy-MM-dd")
        cat = self.category_filter.currentData()
        card = self.card_filter.currentData()
        op_type = self.op_type_filter.currentData() or "all"
        return {
            "query": self.search_edit.text().strip(),
            "date_from": date_from,
            "date_to": date_to,
            "category": cat,
            "card_number": card,
            "operation_type": op_type,
        }

    def _refresh_filter_combos(self):
        """Обновить комбобоксы категорий и карт."""
        cats = db.get_distinct_categories(self._conn)
        self.category_filter.clear()
        self.category_filter.addItem("— Все категории —", None)
        for c in sorted(cats):
            self.category_filter.addItem(c, c)
        cards = db.get_distinct_cards(self._conn)
        self.card_filter.clear()
        self.card_filter.addItem("— Все карты —", None)
        for c in cards:
            self.card_filter.addItem(c or "—", c)

    def _on_search(self):
        self._reload_table()

    def _reload_table(self):
        """Заполнить таблицу из БД с учётом фильтров."""
        filters = self._get_search_filters()
        rows = db.search_transactions(self._conn, **filters)
        self.model.removeRows(0, self.model.rowCount())
        for row in rows:
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
        for r in range(self.model.rowCount()):
            it0 = self.model.item(r, 0)
            if it0:
                it0.setEditable(False)  # Дата — только чтение
        self._refresh_recommendations()

    def _refresh_recommendations(self):
        """Обновить панель рекомендаций (цель + rule-based)."""
        while self.recommendations_content_layout.count():
            child = self.recommendations_content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        # Сначала блок рекомендаций по цели (если есть)
        if self._last_goal_result:
            text, from_ai = self._last_goal_result
            goal_title = QLabel("Сгенерировано ИИ" if from_ai else "Расчёт без облачного ИИ")
            goal_title.setFont(QFont(goal_title.font().family(), 9, QFont.Bold))
            goal_title.setStyleSheet("color: gray;" if not from_ai else "")
            self.recommendations_content_layout.addWidget(goal_title)
            goal_text = QLabel(text)
            goal_text.setWordWrap(True)
            goal_text.setStyleSheet("font-size: 11px;")
            self.recommendations_content_layout.addWidget(goal_text)
            self.recommendations_content_layout.addSpacing(16)
        recs = financial_agent.get_recommendations(self._conn)
        if not recs and not self._last_goal_result:
            hint = QLabel("Недостаточно данных для анализа.\nЗагрузите CSV с транзакциями.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color: gray;")
            self.recommendations_content_layout.addWidget(hint)
        elif recs:
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

    def _on_advice_request(self):
        """Запрос рекомендаций «как сократить расходы» (в фоне — ИИ)."""
        from financial_agent import build_llm_metrics
        metrics = build_llm_metrics(self._conn)
        recs = financial_agent.get_recommendations(self._conn)
        rule_text = "\n\n".join(f"{r.text}\n{r.why}" for r in recs) if recs else "Недостаточно данных для анализа."
        api_config = None
        models = db.get_active_models(self._conn)
        if models:
            m = models[0]
            key = (m.get("api_key") or "").strip()
            if "=" in key:
                key = key.split("=", 1)[1].strip()
            if not key:
                import os
                key = os.environ.get(m.get("api_id", ""), "")
            if key:
                api_config = {
                    "api_url": m.get("api_url"),
                    "api_key": key,
                    "model": m.get("name"),
                    "timeout": int(db.get_setting(self._conn, "request_timeout") or 60),
                }
        self.advice_request_btn.setEnabled(False)
        self._goal_worker.metrics = metrics
        self._goal_worker.rule_text = rule_text
        self._goal_worker.consent = self.advice_consent_check.isChecked()
        self._goal_worker.api_config = api_config
        self._goal_thread.start()

    def _on_goal_finished(self, payload):
        """Показать результат в окне «Финансовые советы»."""
        self._goal_thread.quit()
        self._goal_thread.wait()
        self.advice_request_btn.setEnabled(True)
        try:
            text, from_ai = payload
        except (TypeError, ValueError):
            text, from_ai = str(payload), False
        self._last_goal_result = (text or "", from_ai)
        self._refresh_recommendations()

    def _on_edit_transaction_focus(self):
        """Фокус на таблице для inline-редактирования."""
        self.table.setFocus()
        idx = self.table.currentIndex()
        if not idx.isValid() and self.model.rowCount() > 0:
            self.table.selectRow(0)
        self.statusBar().showMessage("Дважды щёлкните по ячейке для редактирования")

    def _on_transaction_data_changed(self, top_left, bottom_right, roles):
        """Auto-save при изменении данных (кроме даты)."""
        if Qt.EditRole not in roles:
            return
        row = top_left.row()
        col = top_left.column()
        if col == 0:
            return  # Дата — только чтение
        id_index = self.model.index(row, 0)
        row_id = self.model.data(id_index, Qt.UserRole)
        if row_id is None:
            return
        try:
            row_id = int(row_id)
        except (ValueError, TypeError):
            return
        kwargs = {}
        if col == 1:
            kwargs["card_number"] = (self.model.data(top_left, Qt.EditRole) or "").strip()
        elif col == 2:
            kwargs["description"] = (self.model.data(top_left, Qt.EditRole) or "").strip()
        elif col == 3:
            try:
                kwargs["amount"] = float(str(self.model.data(top_left, Qt.EditRole)).replace(",", "."))
            except (ValueError, TypeError):
                return
        elif col == 4:
            kwargs["category"] = (self.model.data(top_left, Qt.EditRole) or "Без категории").strip()
        if kwargs and db.update_transaction(self._conn, row_id, **kwargs):
            self.statusBar().showMessage("Сохранено")
            self._refresh_recommendations()

    def _on_delete_transaction(self):
        """Удалить выделенную транзакцию."""
        idx = self.table.currentIndex()
        if not idx.isValid():
            self.statusBar().showMessage("Выберите строку для удаления")
            return
        row_id = self.model.index(idx.row(), 0).data(Qt.UserRole)
        if row_id is None:
            return
        if QMessageBox.question(
            self, "Подтверждение", "Удалить выбранную транзакцию?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        if db.delete_transaction(self._conn, int(row_id)):
            self._reload_table()
            self.statusBar().showMessage("Транзакция удалена")

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
            new_rows, conflicts = csv_import.check_csv_conflicts(self._conn, path)
            if conflicts:
                reply = QMessageBox.question(
                    self,
                    "Конфликты при импорте",
                    f"Найдено {len(conflicts)} конфликт(ов): данные в CSV отличаются от записей в БД. "
                    "Перезаписать существующие записи данными из CSV?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    self.statusBar().showMessage("Импорт отменён (конфликты)")
                    return
                n = csv_import.import_from_csv(self._conn, path, overwrite_conflicts=True)
            else:
                n = csv_import.import_from_csv(self._conn, path)
            self._refresh_filter_combos()
            self._reload_table()
            self.statusBar().showMessage(f"Загружено записей: {n}")
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка: {e}")

    def _on_show_charts(self):
        self.tabs.setCurrentWidget(self.charts_tab)
        self._refresh_charts()

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) == self.charts_tab:
            self._refresh_charts()
        elif self.tabs.widget(index) == self.goals_tab:
            self._load_goals()
        elif self.tabs.widget(index) == self.overview_tab:
            self._load_overview()

    def _load_goals(self):
        """Загрузить таблицу целей."""
        from datetime import date, datetime
        goals = db.get_all_goals(self._conn)
        self.goals_table.setRowCount(len(goals))
        today = date.today()
        for i, g in enumerate(goals):
            target = float(g.get("target_amount", 0))
            progress_val = float(g.get("current_progress", 0))
            end_s = g.get("end_date", "")[:10]
            try:
                end = datetime.strptime(end_s, "%Y-%m-%d").date()
                months = max(1, (end.year - today.year) * 12 + (end.month - today.month))
                monthly = round(max(0, target - progress_val) / months, 2) if months else 0
            except (ValueError, TypeError):
                monthly = 0
            pct = round(progress_val / target * 100, 1) if target > 0 else 0
            self.goals_table.setItem(i, 0, QTableWidgetItem(str(g.get("description", ""))))
            self.goals_table.setItem(i, 1, QTableWidgetItem(f"{target:,.0f}".replace(",", " ")))
            self.goals_table.setItem(i, 2, QTableWidgetItem(g.get("start_date", "")[:10]))
            self.goals_table.setItem(i, 3, QTableWidgetItem(g.get("end_date", "")[:10]))
            self.goals_table.setItem(i, 4, QTableWidgetItem(f"{progress_val:,.0f}".replace(",", " ")))
            self.goals_table.setItem(i, 5, QTableWidgetItem(f"{monthly:,.0f}".replace(",", " ")))
            pb = QProgressBar()
            pb.setMaximum(100)
            pb.setValue(min(100, int(pct)))
            pb.setMaximumWidth(120)
            self.goals_table.setCellWidget(i, 6, pb)
            self.goals_table.item(i, 0).setData(Qt.UserRole, g.get("id"))

    def _on_add_goal(self):
        from goal_dialog import GoalEditDialog
        dlg = GoalEditDialog(self, conn=self._conn, mode="add")
        if dlg.exec_() == dlg.Accepted:
            self._load_goals()

    def _on_edit_goal(self):
        row = self.goals_table.currentRow()
        if row < 0:
            self.statusBar().showMessage("Выберите цель")
            return
        gid = self.goals_table.item(row, 0).data(Qt.UserRole)
        if not gid:
            return
        goal = db.get_goal_by_id(self._conn, int(gid))
        if not goal:
            return
        from goal_dialog import GoalEditDialog
        dlg = GoalEditDialog(self, conn=self._conn, mode="edit", goal_data=goal)
        if dlg.exec_() == dlg.Accepted:
            self._load_goals()

    def _on_delete_goal(self):
        row = self.goals_table.currentRow()
        if row < 0:
            self.statusBar().showMessage("Выберите цель")
            return
        gid = self.goals_table.item(row, 0).data(Qt.UserRole)
        if not gid:
            return
        if QMessageBox.question(
            self, "Подтверждение", "Удалить выбранную цель?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        if db.delete_goal(self._conn, int(gid)):
            self._load_goals()

    def _save_setting(self, key: str, value: str):
        db.set_setting(self._conn, key, value)
        self.statusBar().showMessage(f"Сохранено: {key}")

    def _on_theme_changed(self, index):
        theme = self.settings_theme.currentData()
        if theme:
            db.set_setting(self._conn, "ui_theme", theme)
            self._apply_theme(theme)

    def _on_font_changed(self, index):
        size = self.settings_font.currentData()
        if size:
            db.set_setting(self._conn, "font_size", size)
            self._apply_font_size(int(size))

    def _apply_theme(self, theme: str):
        from PyQt5.QtGui import QPalette, QColor
        app = QApplication.instance()
        if theme == "dark":
            p = QPalette()
            p.setColor(QPalette.Window, QColor(53, 53, 53))
            p.setColor(QPalette.WindowText, QColor(255, 255, 255))
            p.setColor(QPalette.Base, QColor(35, 35, 35))
            p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            p.setColor(QPalette.Text, QColor(255, 255, 255))
            p.setColor(QPalette.Button, QColor(53, 53, 53))
            p.setColor(QPalette.ButtonText, QColor(255, 255, 255))
            app.setPalette(p)
        else:
            app.setPalette(app.style().standardPalette())

    def _apply_font_size(self, size: int):
        f = QApplication.instance().font()
        f.setPointSize(size)
        QApplication.instance().setFont(f)

    def _on_card_account_type_changed(self, card_number: str, account_type: str):
        """Сохранение типа счёта при выборе в dropdown."""
        db.set_card_account_type(self._conn, card_number, account_type)
        self.statusBar().showMessage(f"Тип счёта для {card_number}: {account_type}")

    def _on_dedup(self):
        n = db.remove_duplicates(self._conn)
        self._reload_table()
        self._refresh_charts()
        self.statusBar().showMessage(f"Удалено дубликатов: {n}")

    def _load_overview(self):
        """Загрузить вкладку «Общее»: по категориям, по картам, по месяцам."""
        year_val = self.overview_year_combo.currentData()
        if year_val is not None:
            date_from = f"{year_val}-01-01"
            date_to = f"{year_val}-12-31"
        else:
            date_from = self.overview_date_from.date().toString("yyyy-MM-dd")
            date_to = self.overview_date_to.date().toString("yyyy-MM-dd")
        while self.overview_content_layout.count():
            child = self.overview_content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        # По категориям
        cat_data = db.get_income_expenses_by_category(self._conn, date_from, date_to)
        total_income = sum(r["income"] for r in cat_data)
        total_exp = sum(r["expenses"] for r in cat_data)
        cat_label = QLabel("По категориям")
        cat_label.setFont(QFont(cat_label.font().family(), 10, QFont.Bold))
        self.overview_content_layout.addWidget(cat_label)
        cat_table = QTableWidget()
        cat_table.setColumnCount(5)
        cat_table.setHorizontalHeaderLabels(["Категория", "Доходы", "Расходы", "% доходов", "% расходов"])
        cat_table.setRowCount(len(cat_data))
        for i, r in enumerate(cat_data):
            inc = float(r["income"])
            exp = float(r["expenses"])
            pct_inc = f"{inc / total_income * 100:.1f}%" if total_income else "—"
            pct_exp = f"{exp / total_exp * 100:.1f}%" if total_exp else "—"
            cat_table.setItem(i, 0, QTableWidgetItem(str(r["category"])))
            cat_table.setItem(i, 1, QTableWidgetItem(f"{inc:,.0f}".replace(",", " ")))
            cat_table.setItem(i, 2, QTableWidgetItem(f"{exp:,.0f}".replace(",", " ")))
            cat_table.setItem(i, 3, QTableWidgetItem(pct_inc))
            cat_table.setItem(i, 4, QTableWidgetItem(pct_exp))
        cat_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.overview_content_layout.addWidget(cat_table)
        self.overview_content_layout.addSpacing(16)
        # По картам
        card_data = db.get_income_expenses_by_card(self._conn, date_from, date_to)
        card_label = QLabel("По картам")
        card_label.setFont(QFont(card_label.font().family(), 10, QFont.Bold))
        self.overview_content_layout.addWidget(card_label)
        card_table = QTableWidget()
        card_table.setColumnCount(6)
        card_table.setHorizontalHeaderLabels(["Карта", "Тип счёта", "Доходы", "Расходы", "% доходов", "% расходов"])
        card_table.setRowCount(len(card_data))
        for i, r in enumerate(card_data):
            card = str(r["card"])
            inc = float(r["income"])
            exp = float(r["expenses"])
            pct_inc = f"{inc / total_income * 100:.1f}%" if total_income else "—"
            pct_exp = f"{exp / total_exp * 100:.1f}%" if total_exp else "—"
            card_table.setItem(i, 0, QTableWidgetItem(card))
            acc_combo = QComboBox()
            acc_combo.addItems(db.ACCOUNT_TYPES)
            current_type = db.get_card_account_type(self._conn, card)
            idx = acc_combo.findText(current_type)
            if idx >= 0:
                acc_combo.setCurrentIndex(idx)
            acc_combo.currentTextChanged.connect(
                lambda t, c=card: self._on_card_account_type_changed(c, t)
            )
            card_table.setCellWidget(i, 1, acc_combo)
            card_table.setItem(i, 2, QTableWidgetItem(f"{inc:,.0f}".replace(",", " ")))
            card_table.setItem(i, 3, QTableWidgetItem(f"{exp:,.0f}".replace(",", " ")))
            card_table.setItem(i, 4, QTableWidgetItem(pct_inc))
            card_table.setItem(i, 5, QTableWidgetItem(pct_exp))
        card_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.overview_content_layout.addWidget(card_table)
        self.overview_content_layout.addSpacing(16)
        # По месяцам (если год)
        if year_val is not None:
            month_data = db.get_income_expenses_by_month(self._conn, year_val)
            if month_data:
                month_label = QLabel("По месяцам")
                month_label.setFont(QFont(month_label.font().family(), 10, QFont.Bold))
                self.overview_content_layout.addWidget(month_label)
                month_table = QTableWidget()
                month_table.setColumnCount(5)
                month_table.setHorizontalHeaderLabels(["Месяц", "Доходы", "Расходы", "Сальдо", "% от года"])
                month_table.setRowCount(len(month_data))
                year_total = sum(float(r["income"]) + float(r["expenses"]) for r in month_data) or 1
                for i, r in enumerate(month_data):
                    inc = float(r["income"])
                    exp = float(r["expenses"])
                    bal = inc - exp
                    pct = (inc + exp) / year_total * 100 if year_total else 0
                    month_table.setItem(i, 0, QTableWidgetItem(str(r["month"])))
                    month_table.setItem(i, 1, QTableWidgetItem(f"{inc:,.0f}".replace(",", " ")))
                    month_table.setItem(i, 2, QTableWidgetItem(f"{exp:,.0f}".replace(",", " ")))
                    month_table.setItem(i, 3, QTableWidgetItem(f"{bal:,.0f}".replace(",", " ")))
                    month_table.setItem(i, 4, QTableWidgetItem(f"{pct:.1f}%"))
                month_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
                self.overview_content_layout.addWidget(month_table)

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
    load_env()
    setup_logging()
    logger.info("Finance AI запуск, версия %s", __version__)
    app = QApplication([])
    conn = db.get_connection()
    db.init_db(conn)
    win = MainWindow(conn)
    win.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
