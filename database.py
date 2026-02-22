"""
Модуль работы с SQLite для Bank Statement Analyzer MVP.
БД: %USERPROFILE%\.bank_analyzer\db.sqlite (кросс-платформенно через pathlib).
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Путь к БД в домашней директории пользователя
DB_DIR = Path.home() / ".bank_analyzer"
DB_PATH = DB_DIR / "db.sqlite"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    description TEXT,
    amount REAL,
    category TEXT DEFAULT 'Без категории',
    card_number TEXT
)
"""

_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """Открытие соединения с БД. Создаёт каталог и файл при первом запуске."""
    global _connection
    if _connection is not None:
        return _connection
    DB_DIR.mkdir(parents=True, exist_ok=True)
    _connection = sqlite3.connect(DB_PATH)
    _connection.row_factory = sqlite3.Row
    return _connection


CREATE_GOALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    target_amount REAL NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    current_progress REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_MODELS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    api_url TEXT NOT NULL,
    api_id TEXT NOT NULL,
    api_key TEXT,
    provider_type TEXT NOT NULL DEFAULT 'custom',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Создание всех таблиц при отсутствии."""
    conn.execute(CREATE_TABLE_SQL)
    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN card_number TEXT")
    except sqlite3.OperationalError:
        pass
    conn.execute(CREATE_GOALS_TABLE_SQL)
    conn.execute(CREATE_MODELS_TABLE_SQL)
    conn.execute(CREATE_SETTINGS_TABLE_SQL)
    try:
        conn.execute("ALTER TABLE models ADD COLUMN api_key TEXT")
    except sqlite3.OperationalError:
        pass
    # Начальные настройки
    default_settings = [
        ("request_timeout", "30", "Таймаут запросов (сек)"),
        ("max_tokens", "2048", "Макс. токенов в ответе"),
        ("ui_theme", "light", "Тема: light/dark"),
        ("font_size", "10", "Размер шрифта"),
    ]
    for k, v, d in default_settings:
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
            (k, v, d),
        )
    conn.commit()


def insert_transactions(
    conn: sqlite3.Connection,
    rows: list[tuple[str, str, float, str, str]],
) -> None:
    """Вставка списка транзакций (date, description, amount, category, card_number)."""
    conn.executemany(
        "INSERT INTO transactions (date, description, amount, category, card_number) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


def update_category(conn: sqlite3.Connection, id: int, category: str) -> None:
    """Обновление категории по id."""
    conn.execute("UPDATE transactions SET category = ? WHERE id = ?", (category, id))
    conn.commit()


def update_transaction(
    conn: sqlite3.Connection,
    id: int,
    *,
    date: Optional[str] = None,
    description: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    card_number: Optional[str] = None,
) -> bool:
    """Обновление транзакции. Возвращает True при успехе."""
    updates: list[tuple[str, Any]] = []
    if date is not None:
        updates.append(("date", date))
    if description is not None:
        updates.append(("description", description))
    if amount is not None:
        updates.append(("amount", amount))
    if category is not None:
        updates.append(("category", category))
    if card_number is not None:
        updates.append(("card_number", card_number))
    if not updates:
        return True
    set_clause = ", ".join(f"{k} = ?" for k, _ in updates)
    values = [v for _, v in updates] + [id]
    cur = conn.execute(f"UPDATE transactions SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return cur.rowcount > 0


def delete_transaction(conn: sqlite3.Connection, id: int) -> bool:
    """Удаление транзакции по id. Возвращает True при успехе."""
    cur = conn.execute("DELETE FROM transactions WHERE id = ?", (id,))
    conn.commit()
    return cur.rowcount > 0


def insert_transaction(
    conn: sqlite3.Connection,
    date: str,
    description: str,
    amount: float,
    category: str = "Без категории",
    card_number: str = "",
) -> int:
    """Вставка одной транзакции. Возвращает id."""
    cur = conn.execute(
        "INSERT INTO transactions (date, description, amount, category, card_number) VALUES (?, ?, ?, ?, ?)",
        (date, description, amount, category, card_number or None),
    )
    conn.commit()
    return cur.lastrowid


def search_transactions(
    conn: sqlite3.Connection,
    *,
    query: str = "",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    category: Optional[str] = None,
    card_number: Optional[str] = None,
    operation_type: str = "all",  # "all" | "income" | "expense"
) -> list[dict[str, Any]]:
    """
    Поиск и фильтрация транзакций.
    query — LIKE по date, description, category, card_number; для amount — диапазон если число.
    """
    conditions: list[str] = []
    params: list[Any] = []
    if date_from:
        conditions.append("date(date) >= date(?)")
        params.append(date_from)
    if date_to:
        conditions.append("date(date) <= date(?)")
        params.append(date_to)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if card_number:
        conditions.append("COALESCE(card_number, '') = ?")
        params.append(card_number.strip())
    if operation_type == "income":
        conditions.append("amount > 0")
    elif operation_type == "expense":
        conditions.append("amount < 0")
    if query and query.strip():
        q = query.strip()
        if q.replace(".", "").replace("-", "").replace(",", "").isdigit():
            try:
                val = float(q.replace(",", "."))
                conditions.append("(amount BETWEEN ? AND ? OR amount BETWEEN ? AND ?)")
                params.extend([val - 0.01, val + 0.01, -val - 0.01, -val + 0.01])
            except ValueError:
                pass
        else:
            pattern = f"%{q}%"
            conditions.append(
                "(date LIKE ? OR description LIKE ? OR category LIKE ? OR card_number LIKE ?)"
            )
            params.extend([pattern, pattern, pattern, pattern])
    where = " AND ".join(conditions) if conditions else "1=1"
    cur = conn.execute(
        f"SELECT id, date, description, amount, category, card_number FROM transactions WHERE {where} ORDER BY date DESC, id DESC",
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def get_all_transactions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Выборка для таблицы: id, date, description, amount, category, card_number."""
    cur = conn.execute(
        "SELECT id, date, description, amount, category, card_number FROM transactions ORDER BY date DESC, id DESC"
    )
    return [dict(row) for row in cur.fetchall()]


def get_existing_keys(conn: sqlite3.Connection) -> set[tuple[str, str, float]]:
    """Ключи уже существующих транзакций (date, description, amount) для отсечения дубликатов при импорте."""
    cur = conn.execute(
        "SELECT date, description, amount FROM transactions"
    )
    return {tuple(row) for row in cur.fetchall()}


def update_card_if_empty(
    conn: sqlite3.Connection, date: str, description: str, amount: float, card_number: str
) -> bool:
    """Обновляет номер карты у существующей записи, если у неё он пустой. Возвращает True, если обновление выполнено."""
    if not (card_number and card_number.strip()):
        return False
    cur = conn.execute(
        """UPDATE transactions SET card_number = ?
           WHERE date = ? AND description = ? AND amount = ?
           AND (card_number IS NULL OR TRIM(card_number) = '')""",
        (card_number.strip(), date, description, amount),
    )
    conn.commit()
    return cur.rowcount > 0


def remove_duplicates(conn: sqlite3.Connection) -> int:
    """Удаляет дубликаты по ключу (date, description, amount). Для каждой группы оставляет одну запись: приоритет у строки с заполненным номером карты, иначе с минимальным id. Возвращает число удалённых строк."""
    cur = conn.execute(
        """
        DELETE FROM transactions
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id,
                    ROW_NUMBER() OVER (
                        PARTITION BY date, description, amount
                        ORDER BY CASE WHEN TRIM(COALESCE(card_number,'')) <> '' THEN 0 ELSE 1 END, id
                    ) AS rn
                FROM transactions
            ) WHERE rn = 1
        )
        """
    )
    deleted = cur.rowcount
    conn.commit()
    return deleted


def get_expenses_by_category_last_month(
    conn: sqlite3.Connection,
) -> list[tuple[str, float]]:
    """Агрегат по категориям за последние 30 дней, только расходы (amount < 0). Сумма по модулю."""
    cur = conn.execute(
        """
        SELECT category, ABS(SUM(amount)) AS total
        FROM transactions
        WHERE amount < 0
          AND date >= date('now', '-30 days')
        GROUP BY category
        ORDER BY total DESC
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def get_expenses_by_day_last_week(
    conn: sqlite3.Connection,
) -> list[tuple[str, float]]:
    """Агрегат по дням за последние 7 дней, только расходы. Сумма по модулю."""
    cur = conn.execute(
        """
        SELECT date(date) AS day, ABS(SUM(amount)) AS total
        FROM transactions
        WHERE amount < 0
          AND date >= date('now', '-7 days')
        GROUP BY date(date)
        ORDER BY day
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def get_income_last_30_days(conn: sqlite3.Connection) -> float:
    """Сумма доходов (amount > 0) за последние 30 дней."""
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE amount > 0 AND date >= date('now', '-30 days')
        """
    )
    return float(cur.fetchone()[0] or 0)


def get_total_expenses_last_30_days(conn: sqlite3.Connection) -> float:
    """Сумма расходов (amount < 0, по модулю) за последние 30 дней."""
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
        WHERE amount < 0 AND date >= date('now', '-30 days')
        """
    )
    return float(cur.fetchone()[0] or 0)


def get_income_last_90_days(conn: sqlite3.Connection) -> float:
    """Сумма доходов (amount > 0) за последние 90 дней."""
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM transactions
        WHERE amount > 0 AND date >= date('now', '-90 days')
        """
    )
    return float(cur.fetchone()[0] or 0)


def get_total_expenses_last_90_days(conn: sqlite3.Connection) -> float:
    """Сумма расходов (amount < 0, по модулю) за последние 90 дней."""
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
        WHERE amount < 0 AND date >= date('now', '-90 days')
        """
    )
    return float(cur.fetchone()[0] or 0)


def get_expenses_by_category_last_90_days(
    conn: sqlite3.Connection,
) -> list[tuple[str, float]]:
    """Агрегат по категориям за последние 90 дней, только расходы (amount < 0). Сумма по модулю."""
    cur = conn.execute(
        """
        SELECT category, ABS(SUM(amount)) AS total
        FROM transactions
        WHERE amount < 0
          AND date >= date('now', '-90 days')
        GROUP BY category
        ORDER BY total DESC
        """
    )
    return [(row[0], row[1]) for row in cur.fetchall()]


def get_expense_sum_by_category_group(
    conn: sqlite3.Connection,
    days: int,
    category_groups: dict[str, list[str]],
) -> dict[str, float]:
    """
    Сумма расходов по именованным группам категорий.
    category_groups: {"подписки": ["Цифровые товары", ...], ...}
    Возвращает {"подписки": 1500.0, ...} (только amount < 0).
    """
    result: dict[str, float] = {name: 0.0 for name in category_groups}
    for group_name, categories in category_groups.items():
        if not categories:
            continue
        placeholders = ",".join("?" * len(categories))
        cur = conn.execute(
            f"""
            SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
            WHERE amount < 0
              AND date >= date('now', ?)
              AND category IN ({placeholders})
            """,
            (f"-{days} days",) + tuple(categories),
        )
        result[group_name] = float(cur.fetchone()[0] or 0)
    return result


def get_expense_trend_weekly(conn: sqlite3.Connection) -> tuple[float, float]:
    """
    (сумма расходов за последние 7 дней, сумма расходов за 7 дней до этого).
    Для сравнения тренда неделя vs предыдущая неделя.
    """
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
        WHERE amount < 0 AND date >= date('now', '-7 days')
        """
    )
    this_week = float(cur.fetchone()[0] or 0)
    cur = conn.execute(
        """
        SELECT COALESCE(SUM(ABS(amount)), 0) FROM transactions
        WHERE amount < 0
          AND date >= date('now', '-14 days')
          AND date < date('now', '-7 days')
        """
    )
    last_week = float(cur.fetchone()[0] or 0)
    return (this_week, last_week)


# --- Goals ---


def create_goal(
    conn: sqlite3.Connection,
    description: str,
    target_amount: float,
    start_date: str,
    end_date: str,
    current_progress: float = 0,
) -> int:
    cur = conn.execute(
        "INSERT INTO goals (description, target_amount, start_date, end_date, current_progress) VALUES (?, ?, ?, ?, ?)",
        (description, target_amount, start_date, end_date, current_progress),
    )
    conn.commit()
    return cur.lastrowid


def update_goal(
    conn: sqlite3.Connection,
    id: int,
    *,
    description: Optional[str] = None,
    target_amount: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_progress: Optional[float] = None,
) -> bool:
    updates: list[tuple[str, Any]] = []
    if description is not None:
        updates.append(("description", description))
    if target_amount is not None:
        updates.append(("target_amount", target_amount))
    if start_date is not None:
        updates.append(("start_date", start_date))
    if end_date is not None:
        updates.append(("end_date", end_date))
    if current_progress is not None:
        updates.append(("current_progress", current_progress))
    if not updates:
        return True
    set_clause = ", ".join(f"{k} = ?" for k, _ in updates)
    values = [v for _, v in updates] + [id]
    cur = conn.execute(f"UPDATE goals SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return cur.rowcount > 0


def delete_goal(conn: sqlite3.Connection, id: int) -> bool:
    cur = conn.execute("DELETE FROM goals WHERE id = ?", (id,))
    conn.commit()
    return cur.rowcount > 0


def get_all_goals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute(
        "SELECT id, description, target_amount, start_date, end_date, current_progress, created_at FROM goals ORDER BY end_date ASC"
    )
    return [dict(row) for row in cur.fetchall()]


def get_goal_by_id(conn: sqlite3.Connection, id: int) -> Optional[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM goals WHERE id = ?", (id,))
    row = cur.fetchone()
    return dict(row) if row else None


# --- Models ---


def add_model(
    conn: sqlite3.Connection,
    name: str,
    api_url: str,
    api_id: str,
    provider_type: str = "custom",
    is_active: int = 1,
    api_key: Optional[str] = None,
) -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO models (name, api_url, api_id, api_key, provider_type, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, api_url, api_id, api_key, provider_type, is_active, now, now),
    )
    conn.commit()
    return cur.lastrowid


def update_model(conn: sqlite3.Connection, model_id: int, **kwargs: Any) -> bool:
    allowed = {"name", "api_url", "api_id", "api_key", "provider_type", "is_active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [model_id]
    cur = conn.execute(f"UPDATE models SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return cur.rowcount > 0


def delete_model(conn: sqlite3.Connection, model_id: int) -> bool:
    cur = conn.execute("DELETE FROM models WHERE id = ?", (model_id,))
    conn.commit()
    return cur.rowcount > 0


def get_all_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM models ORDER BY name")
    return [dict(row) for row in cur.fetchall()]


def get_active_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM models WHERE is_active = 1 ORDER BY name")
    return [dict(row) for row in cur.fetchall()]


# --- Settings ---


def get_setting(conn: sqlite3.Connection, key: str) -> Optional[str]:
    cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    return row["value"] if row else None


def set_setting(
    conn: sqlite3.Connection, key: str, value: str, description: Optional[str] = None
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO settings (key, value, description, updated_at) VALUES (?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        (key, value, description or "", now),
    )
    conn.commit()


# --- Aggregates for "Общее" tab ---


def get_income_expenses_by_category(
    conn: sqlite3.Connection, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    """Доходы и расходы по категориям за период."""
    cur = conn.execute(
        """
        SELECT category,
               COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS income,
               COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE date(date) >= date(?) AND date(date) <= date(?)
        GROUP BY category
        ORDER BY expenses DESC, income DESC
        """,
        (date_from, date_to),
    )
    return [dict(row) for row in cur.fetchall()]


def get_income_expenses_by_card(
    conn: sqlite3.Connection, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    """Доходы и расходы по картам за период."""
    cur = conn.execute(
        """
        SELECT COALESCE(card_number, '—') AS card,
               COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS income,
               COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE date(date) >= date(?) AND date(date) <= date(?)
        GROUP BY card_number
        ORDER BY expenses DESC, income DESC
        """,
        (date_from, date_to),
    )
    return [dict(row) for row in cur.fetchall()]


def get_income_expenses_by_month(
    conn: sqlite3.Connection, year: int
) -> list[dict[str, Any]]:
    """Разбивка по месяцам за год."""
    cur = conn.execute(
        """
        SELECT strftime('%Y-%m', date) AS month,
               COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) AS income,
               COALESCE(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 0) AS expenses
        FROM transactions
        WHERE strftime('%Y', date) = ?
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month
        """,
        (str(year),),
    )
    return [dict(row) for row in cur.fetchall()]


def get_distinct_categories(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category")
    return [row[0] for row in cur.fetchall()]


def get_distinct_cards(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT card_number FROM transactions WHERE TRIM(COALESCE(card_number, '')) <> '' ORDER BY card_number")
    return [row[0] or "" for row in cur.fetchall()]
