"""
Импорт банковских выписок Тинькофф из CSV в БД.
Формат образца: Дата операции, Дата платежа, Номер карты, Статус, Сумма операции,
Валюта операции, ..., Категория, MCC, Описание, ...
В БД идут: дата, описание (Описание), сумма (Сумма операции), категория (Категория или по умолчанию).
"""
import sqlite3
from pathlib import Path

import pandas as pd

from database import get_existing_keys, insert_transactions, update_card_if_empty


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


def import_from_csv(conn: sqlite3.Connection, path: str | Path) -> int:
    """
    Парсит CSV Тинькофф (формат как в Primer.csv), вставляет транзакции в БД.
    Возвращает количество загруженных строк.
    """
    path = Path(path)
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
    df = _normalize_columns(df)

    required = {"date", "description", "amount"}
    if not required.issubset(df.columns):
        missing = required - set(df.columns)
        raise ValueError(f"В CSV не найдены столбцы: {missing}. Есть: {list(df.columns)}")

    # Дата: ДД.ММ.ГГГГ ЧЧ:ММ:СС или ДД.ММ.ГГГГ
    date_series = pd.to_datetime(
        df["date"].astype(str).str.strip(),
        format="mixed",
        dayfirst=True,
    )
    df["date_iso"] = date_series.dt.strftime("%Y-%m-%d %H:%M:%S")

    # Сумма: запятая как десятичный разделитель
    amount_series = df["amount"].astype(str).str.strip().str.replace(",", ".", regex=False)
    df["amount_float"] = pd.to_numeric(amount_series, errors="coerce").fillna(0).astype(float)

    # Категория: из CSV или «Без категории»
    if "category" in df.columns:
        df["category"] = df["category"].fillna("Без категории").astype(str).str.strip()
    else:
        df["category"] = "Без категории"

    # Номер карты: из CSV или пусто
    if "card_number" not in df.columns:
        df["card_number"] = ""
    else:
        df["card_number"] = df["card_number"].fillna("").astype(str).str.strip()

    rows = list(
        zip(
            df["date_iso"].tolist(),
            df["description"].fillna("").astype(str).tolist(),
            df["amount_float"].tolist(),
            df["category"].tolist(),
            df["card_number"].tolist(),
        )
    )
    # Убираем дубликаты: не вставляем строки с ключом (date, description, amount), уже есть в БД.
    # Если запись уже есть, но без номера карты — подставляем номер из CSV.
    existing = get_existing_keys(conn)
    new_rows = []
    cards_updated = 0
    for r in rows:
        key = (r[0], r[1], r[2])
        card = (r[4] or "").strip()
        if key not in existing:
            new_rows.append(r)
            existing.add(key)
        elif card and update_card_if_empty(conn, r[0], r[1], r[2], card):
            cards_updated += 1
    insert_transactions(conn, new_rows)
    return len(new_rows)
