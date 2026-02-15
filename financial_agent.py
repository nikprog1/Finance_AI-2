"""
AI-агент финансового состояния (rule-based).
Собирает агрегаты из БД, прогоняет правила, возвращает 1–3 рекомендации.
Работает полностью локально, без внешних API.
"""
import sqlite3

import database as db
from agent_rules import ALL_RULES, CATEGORY_GROUPS, Recommendation


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
