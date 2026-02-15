"""
Модуль работы с SQLite для Bank Statement Analyzer MVP.
БД: %USERPROFILE%\.bank_analyzer\db.sqlite (кросс-платформенно через pathlib).
"""
import sqlite3
from pathlib import Path
from typing import Any

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


def init_db(conn: sqlite3.Connection) -> None:
    """Создание таблицы transactions при отсутствии. Добавляет card_number, если таблица уже была."""
    conn.execute(CREATE_TABLE_SQL)
    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN card_number TEXT")
    except sqlite3.OperationalError:
        pass  # колонка уже есть
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
