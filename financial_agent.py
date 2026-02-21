"""
AI-агент финансового состояния (rule-based + опционально LLM).
Собирает агрегаты из БД, прогоняет правила, возвращает 1–3 рекомендации.
"""
import sqlite3
from datetime import date, datetime
from typing import Any

import database as db
from agent_rules import ALL_RULES, CATEGORY_GROUPS, Recommendation


def build_llm_metrics(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Собирает анонимизированные метрики для LLM (только агрегаты, без сырых транзакций).
    """
    income = db.get_income_last_30_days(conn)
    expenses = db.get_total_expenses_last_30_days(conn)
    savings = max(0.0, income - expenses)
    expense_by_group = db.get_expense_sum_by_category_group(
        conn, days=30, category_groups=CATEGORY_GROUPS
    )
    this_week, last_week = db.get_expense_trend_weekly(conn)
    change_pct = round((this_week - last_week) / last_week * 100, 1) if last_week else 0.0
    top_cats = db.get_expenses_by_category_last_month(conn)[:5]
    metrics = {
        "period_days": 30,
        "income_rub": round(income, 2),
        "expenses_rub": round(expenses, 2),
        "savings_rub": round(savings, 2),
        "expenses_by_group": {k: round(v, 2) for k, v in expense_by_group.items()},
        "expense_trend": {
            "this_week_rub": round(this_week, 2),
            "last_week_rub": round(last_week, 2),
            "change_percent": change_pct,
        },
        "top_categories": [{"name": c, "amount_rub": round(a, 2)} for c, a in top_cats],
    }
    return metrics


def build_goal_metrics(
    conn: sqlite3.Connection,
    target_amount: float,
    target_date: str,
) -> dict[str, Any]:
    """
    Анонимизированные метрики для финансовой цели (за 90 дней).
    Без описаний, номеров карт, имён.
    """
    income_90d = db.get_income_last_90_days(conn)
    expenses_90d = db.get_total_expenses_last_90_days(conn)
    top_cats = db.get_expenses_by_category_last_90_days(conn)[:10]
    monthly_income = round(income_90d / 3, 2) if income_90d else 0.0
    monthly_expenses = round(expenses_90d / 3, 2) if expenses_90d else 0.0
    current_savings = max(0.0, round(income_90d - expenses_90d, 2))
    return {
        "target_amount": round(float(target_amount), 2),
        "target_date": target_date,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "top_categories": [c for c, _ in top_cats],
        "current_savings": current_savings,
    }


def calc_goal_monthly_savings(
    target_amount: float,
    target_date: str,
    current_savings: float,
) -> tuple[float, str]:
    """
    Rule-based расчёт: сколько откладывать в месяц до даты.
    Возвращает (руб/мес, текст подсказки).
    """
    try:
        if isinstance(target_date, str):
            end = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
        else:
            end = target_date
    except (ValueError, TypeError):
        return 0.0, "Неверный формат даты. Используйте ГГГГ-ММ-ДД."

    today = date.today()
    if end <= today:
        return 0.0, "Дата окончания должна быть в будущем."

    months = max(1, (end.year - today.year) * 12 + (end.month - today.month))
    remaining = max(0.0, float(target_amount) - float(current_savings))
    monthly = round(remaining / months, 2) if months else 0.0
    date_str = end.strftime("%d.%m.%Y")
    return monthly, f"Ежемесячно нужно откладывать {int(monthly)} ₽ до {date_str}. Данных для детального анализа недостаточно."


def get_llm_recommendation(conn: sqlite3.Connection) -> str | None:
    """
    Генерирует один совет через локальную Llama по анонимизированным метрикам.
    При недоступности модели возвращает None (graceful degradation).
    """
    try:
        from llm_agent import get_agent
        metrics = build_llm_metrics(conn)
        return get_agent().generate_advice(metrics)
    except Exception:
        return None


def get_recommendations(conn: sqlite3.Connection) -> list[Recommendation]:
    """
    Генерирует до 3 персонализированных рекомендаций на основе загруженных данных.
    """
    # 1. Собрать агрегаты
    income_30d = db.get_income_last_30_days(conn)
    expense_by_group = db.get_expense_sum_by_category_group(
        conn, days=30, category_groups=CATEGORY_GROUPS
    )
    expense_this_week, expense_last_week = db.get_expense_trend_weekly(conn)

    aggregates = {
        "income_30d": income_30d,
        "expense_this_week": expense_this_week,
        "expense_last_week": expense_last_week,
        **expense_by_group,
    }

    # 2. Прогнать правила, собрать сработавшие
    recommendations: list[Recommendation] = []
    for rule_fn in ALL_RULES:
        if len(recommendations) >= 3:
            break
        rec = rule_fn(aggregates)
        if rec is not None:
            recommendations.append(rec)

    return recommendations
