"""
AI-агент финансового состояния (rule-based + опционально LLM).
Собирает агрегаты из БД, прогоняет правила, возвращает 1–3 рекомендации.
"""
import sqlite3
from datetime import date, datetime
from typing import Any

import database as db
from agent_rules import ALL_RULES, CATEGORY_GROUPS, Recommendation


def build_llm_metrics(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Собирает анонимизированные метрики для LLM (только агрегаты, без сырых транзакций).
    Если заданы date_from и date_to — берутся данные за этот период (обычно с вкладки «Отчеты»).
    Иначе — за последние 30 дней.
    """
    if date_from and date_to:
        income = db.get_income_for_period(conn, date_from, date_to)
        expenses = db.get_total_expenses_for_period(conn, date_from, date_to)
        expense_by_group = db.get_expense_sum_by_category_group_for_period(
            conn, date_from, date_to, CATEGORY_GROUPS
        )
        first_half, second_half, change_pct = db.get_expense_trend_for_period(
            conn, date_from, date_to
        )
        top_cats = db.get_expenses_by_category_for_period(
            conn, date_from, date_to
        )[:5]
        from datetime import datetime
        d1 = datetime.strptime(date_from[:10], "%Y-%m-%d")
        d2 = datetime.strptime(date_to[:10], "%Y-%m-%d")
        period_days = max(1, (d2 - d1).days)
        expense_trend = {
            "this_week_rub": round(second_half, 2),
            "last_week_rub": round(first_half, 2),
            "change_percent": change_pct,
        }
    else:
        income = db.get_income_last_30_days(conn)
        expenses = db.get_total_expenses_last_30_days(conn)
        expense_by_group = db.get_expense_sum_by_category_group(
            conn, days=30, category_groups=CATEGORY_GROUPS
        )
        this_week, last_week = db.get_expense_trend_weekly(conn)
        change_pct = round((this_week - last_week) / last_week * 100, 1) if last_week else 0.0
        top_cats = db.get_expenses_by_category_last_month(conn)[:5]
        period_days = 30
        expense_trend = {
            "this_week_rub": round(this_week, 2),
            "last_week_rub": round(last_week, 2),
            "change_percent": change_pct,
        }
    savings = max(0.0, income - expenses)
    if date_from and date_to:
        d1 = datetime.strptime(date_from[:10], "%Y-%m-%d")
        d2 = datetime.strptime(date_to[:10], "%Y-%m-%d")
        period_str = f"{d1.strftime('%d.%m.%Y')} — {d2.strftime('%d.%m.%Y')}"
    else:
        period_str = "последние 30 дней"
    metrics = {
        "period_days": period_days,
        "period": period_str,
        "income_rub": round(income, 2),
        "expenses_rub": round(expenses, 2),
        "savings_rub": round(savings, 2),
        "expenses_by_group": {k: round(v, 2) for k, v in expense_by_group.items()},
        "expense_trend": expense_trend,
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


def build_goals_portfolio_metrics(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Собирает агрегированный payload по всем финансовым целям пользователя.
    Использует период со вкладки «Отчеты» для общего финансового контекста.
    """
    summary = build_llm_metrics(conn, date_from=date_from, date_to=date_to)
    goals = db.get_all_goals(conn)
    today = date.today()
    goals_payload: list[dict[str, Any]] = []

    for goal in goals:
        target_amount = round(float(goal.get("target_amount", 0) or 0), 2)
        current_progress = round(float(goal.get("current_progress", 0) or 0), 2)
        remaining_amount = round(max(0.0, target_amount - current_progress), 2)
        start_date = (goal.get("start_date") or "")[:10]
        end_date = (goal.get("end_date") or "")[:10]
        progress_pct = round(current_progress / target_amount * 100, 1) if target_amount > 0 else 0.0

        months_left = 0
        target_date_str = end_date
        if target_date_str:
            try:
                end = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                if end > today:
                    months_left = max(1, (end.year - today.year) * 12 + (end.month - today.month))
            except ValueError:
                months_left = 0

        monthly_required = round(remaining_amount / months_left, 2) if months_left else 0.0
        status = "достигнута" if remaining_amount <= 0 else "в процессе"
        if target_date_str:
            try:
                end = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                if end <= today and remaining_amount > 0:
                    status = "срок истек"
            except ValueError:
                pass

        goals_payload.append({
            "name": str(goal.get("description") or "Без названия"),
            "target_amount": target_amount,
            "current_amount": current_progress,
            "remaining_amount": remaining_amount,
            "start_date": start_date,
            "deadline": end_date,
            "months_left": months_left,
            "required_per_month": monthly_required,
            "progress_percent": progress_pct,
            "status": status,
        })

    period_days = int(summary.get("period_days") or 30)
    month_factor = max(1.0, period_days / 30.0)
    monthly_income = round(float(summary.get("income_rub") or 0) / month_factor, 2)
    monthly_expenses = round(float(summary.get("expenses_rub") or 0) / month_factor, 2)
    monthly_surplus = round(max(0.0, monthly_income - monthly_expenses), 2)
    total_required_per_month = round(sum(goal["required_per_month"] for goal in goals_payload), 2)

    return {
        "report_period": summary.get("period"),
        "goals_count": len(goals_payload),
        "goals": goals_payload,
        "context": {
            "income_rub": summary.get("income_rub", 0.0),
            "expenses_rub": summary.get("expenses_rub", 0.0),
            "savings_rub": summary.get("savings_rub", 0.0),
            "estimated_monthly_income_rub": monthly_income,
            "estimated_monthly_expenses_rub": monthly_expenses,
            "available_monthly_surplus_rub": monthly_surplus,
            "total_required_per_month_rub": total_required_per_month,
            "top_categories": summary.get("top_categories", []),
        },
    }


def build_goals_portfolio_fallback(
    conn: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """
    Краткий rule-based текст на случай, если облачный ИИ недоступен.
    """
    payload = build_goals_portfolio_metrics(conn, date_from=date_from, date_to=date_to)
    goals = payload.get("goals", [])
    if not goals:
        return "Добавьте хотя бы одну финансовую цель, чтобы получить анализ плана."

    nearest_goal = min(
        goals,
        key=lambda item: (
            item.get("deadline") == "",
            item.get("deadline") or "9999-12-31",
        ),
    )
    surplus = float(payload["context"].get("available_monthly_surplus_rub", 0.0) or 0.0)
    total_required = float(payload["context"].get("total_required_per_month_rub", 0.0) or 0.0)
    feasibility = "план выглядит напряженным"
    if total_required <= 0:
        feasibility = "активные накопления по целям сейчас не требуются"
    elif surplus >= total_required:
        feasibility = "план выглядит реалистичным"

    nearest_deadline = nearest_goal.get("deadline") or "без срока"
    if nearest_deadline != "без срока":
        try:
            nearest_deadline = datetime.strptime(nearest_deadline, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
    nearest_amount = float(nearest_goal.get("required_per_month", 0.0) or 0.0)
    return (
        f"Период: {payload.get('report_period')}. "
        f"Ближайшая цель «{nearest_goal.get('name')}» требует около {nearest_amount:,.0f} ₽ в месяц до {nearest_deadline}. "
        f"Суммарно по всем целям нужно около {total_required:,.0f} ₽ в месяц, при этом {feasibility}."
    ).replace(",", " ")


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
