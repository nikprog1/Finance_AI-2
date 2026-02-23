"""
Импорт банковских выписок Тинькофф из CSV в БД.
Формат образца: Дата операции, Дата платежа, Номер карты, Статус, Сумма операции,
Валюта операции, ..., Категория, MCC, Описание, ...
В БД идут: дата, описание (Описание), сумма (Сумма операции), категория (Категория или по умолчанию).
"""
import sqlite3
from pathlib import Path

import pandas as pd

from database import (
    get_existing_by_datetime,
    get_existing_keys,
    insert_transactions,
    update_card_if_empty,
    update_transaction,
)


def _find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    """Найти имя столбца в DataFrame по одному из вариантов (без учёта регистра и пробелов)."""
    cols_lower = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in cols_lower:
            return cols_lower[key]
    return None


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Приведение к каноническим именам.
    Приоритет: точные названия столбцов Тинькофф (Дата операции, Описание, Сумма операции, Категория).
    """
    # Убираем кавычки из названий столбцов, если есть
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    mapping = {}
    # Дата — только «Дата операции», не «Дата платежа»
    date_col = _find_column(df, "Дата операции")
    if date_col:
        mapping[date_col] = "date"
    # Описание — столбец «Описание» (контрагент/назначение)
    desc_col = _find_column(df, "Описание", "Описание операции")
    if desc_col:
        mapping[desc_col] = "description"
    # Сумма — только «Сумма операции»
    amount_col = _find_column(df, "Сумма операции")
    if amount_col:
        mapping[amount_col] = "amount"
    # Категория из выписки (если есть)
    cat_col = _find_column(df, "Категория")
    if cat_col:
        mapping[cat_col] = "category"
    # Номер карты (например *5436)
    card_col = _find_column(df, "Номер карты")
    if card_col:
        mapping[card_col] = "card_number"
    df = df.rename(columns=mapping)
    return df


def _parse_csv_rows(path: str | Path) -> list[tuple]:
    """Парсит CSV и возвращает список строк (date_iso, description, amount, category, card_number)."""
    path = Path(path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df = _normalize_columns(df)

    required = {"date", "description", "amount"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"В CSV не найдены столбцы: {missing}. Есть: {list(df.columns)}")

    date_series = pd.to_datetime(
        df["date"].astype(str).str.strip(),
        format="mixed",
        dayfirst=True,
    )
    df["date_iso"] = date_series.dt.strftime("%Y-%m-%d %H:%M:%S")

    amount_series = df["amount"].astype(str).str.strip().str.replace(",", ".", regex=False)
    df["amount_float"] = pd.to_numeric(amount_series, errors="coerce").fillna(0).astype(float)

    if "category" in df.columns:
        df["category"] = df["category"].fillna("Без категории").astype(str).str.strip()
    else:
        df["category"] = "Без категории"

    if "card_number" not in df.columns:
        df["card_number"] = ""
    else:
        df["card_number"] = df["card_number"].fillna("").astype(str).str.strip()

    return list(
        zip(
            df["date_iso"].tolist(),
            df["description"].fillna("").astype(str).tolist(),
            df["amount_float"].tolist(),
            df["category"].tolist(),
            df["card_number"].tolist(),
        )
    )


def check_csv_conflicts(conn: sqlite3.Connection, path: str | Path) -> tuple[list, list]:
    """
    Проверяет CSV на конфликты: дата и время совпадают, но одно из полей (description, amount, category, card_number) отличается.
    Возвращает (new_rows, conflicts).
    """
    rows = _parse_csv_rows(path)
    existing = get_existing_by_datetime(conn)
    new_rows = []
    conflicts = []
    for r in rows:
        date_iso = r[0]
        desc_csv = (r[1] or "").strip()
        amt_csv = r[2]
        cat_csv = (r[3] or "Без категории").strip()
        card_csv = (r[4] or "").strip()
        if date_iso not in existing:
            new_rows.append(r)
            continue
        for db_row in existing[date_iso]:
            desc_db = (db_row.get("description") or "").strip()
            amt_db = db_row.get("amount", 0)
            cat_db = (db_row.get("category") or "Без категории").strip()
            card_db = (db_row.get("card_number") or "").strip()
            differs = (
                desc_csv != desc_db
                or abs(float(amt_csv) - float(amt_db)) > 1e-9
                or cat_csv != cat_db
                or card_csv != card_db
            )
            if differs:
                conflicts.append({
                    "csv_row": {"date": date_iso, "description": desc_csv, "amount": amt_csv, "category": cat_csv, "card_number": card_csv},
                    "db_row": {"id": db_row["id"], "description": desc_db, "amount": amt_db, "category": cat_db, "card_number": card_db},
                })
            break  # конфликт с первым совпадением по дате
    return new_rows, conflicts


def import_from_csv(conn: sqlite3.Connection, path: str | Path, overwrite_conflicts: bool = False) -> int:
    """
    Парсит CSV Тинькофф, вставляет транзакции в БД.
    При overwrite_conflicts=True перезаписывает конфликтующие записи (совпадение по дате+времени, различие полей).
    Возвращает количество загруженных/обновлённых строк.
    """
    rows = _parse_csv_rows(path)
    existing = get_existing_by_datetime(conn)
    new_rows = []
    updated = 0
    for r in rows:
        date_iso = r[0]
        desc_csv = (r[1] or "").strip()
        amt_csv = r[2]
        cat_csv = (r[3] or "Без категории").strip()
        card_csv = (r[4] or "").strip()
        if date_iso not in existing:
            new_rows.append(r)
            continue
        db_rows = existing[date_iso]
        for db_row in db_rows:
            desc_db = (db_row.get("description") or "").strip()
            amt_db = db_row.get("amount", 0)
            cat_db = (db_row.get("category") or "Без категории").strip()
            card_db = (db_row.get("card_number") or "").strip()
            differs = (
                desc_csv != desc_db
                or abs(float(amt_csv) - float(amt_db)) > 1e-9
                or cat_csv != cat_db
                or card_csv != card_db
            )
            if differs and overwrite_conflicts:
                update_transaction(
                    conn,
                    db_row["id"],
                    description=desc_csv,
                    amount=float(amt_csv),
                    category=cat_csv,
                    card_number=card_csv,
                )
                updated += 1
            elif not differs and card_csv and not card_db:
                if update_card_if_empty(conn, r[0], r[1], r[2], card_csv):
                    updated += 1
            break  # обрабатываем первое совпадение по дате
    insert_transactions(conn, new_rows)
    return len(new_rows) + updated
