"""
Rule-based правила для AI-агента финансового состояния.
Каждое правило — функция (aggregates) -> Recommendation | None.
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class Recommendation:
    text: str
    why: str
    metric: str


# Группы категорий для агрегации (подстраиваются под выписки Тинькофф и др.)
CATEGORY_GROUPS = {
    "подписки": [
        "Цифровые товары",
        "Экосистема Яндекс",
        "Мобильная связь",
        "Услуги банка",
    ],
    "продукты": ["Супермаркеты"],
    "фастфуд": ["Фастфуд"],
}


def rule_subscriptions_share_of_income(agg: dict[str, Any]) -> Recommendation | None:
    """Подписки от дохода > 15%."""
    income = agg.get("income_30d") or 0
    subscriptions = agg.get("подписки") or 0
    if income <= 0 or subscriptions <= 0:
        return None
    pct = round(subscriptions / income * 100, 1)
    if pct <= 15:
        return None
    return Recommendation(
        text=f"Вы тратите {pct}% дохода на подписки.",
        why="Рекомендуемая доля — до 15%. Сокращение подписок освобождает средства для сбережений.",
        metric="subscriptions_share",
    )


def rule_fastfood_share_of_food(agg: dict[str, Any]) -> Recommendation | None:
    """Фастфуд/кафе > 30% от расходов на продукты."""
    products = agg.get("продукты") or 0
    fastfood = agg.get("фастфуд") or 0
    if products <= 0 or fastfood <= 0:
        return None
    pct = round(fastfood / (products + fastfood) * 100, 1)
    if pct <= 30:
        return None
    return Recommendation(
        text=f"{pct}% расходов на еду — фастфуд и кафе.",
        why="Домашняя еда обычно дешевле и полезнее. Можно сократить расходы, готовя дома.",
        metric="fastfood_share",
    )


def rule_expense_trend_increase(agg: dict[str, Any]) -> Recommendation | None:
    """Расходы выросли > 20% по сравнению с прошлой неделей."""
    this_week = agg.get("expense_this_week") or 0
    last_week = agg.get("expense_last_week") or 0
    if last_week <= 0 or this_week <= 0:
        return None
    pct = round((this_week - last_week) / last_week * 100, 1)
    if pct <= 20:
        return None
    return Recommendation(
        text=f"Расходы выросли на {pct}% по сравнению с прошлой неделей.",
        why="Резкий рост может указывать на незапланированные траты. Проверьте крупные операции.",
        metric="expense_trend",
    )


def rule_subscriptions_high_absolute(agg: dict[str, Any]) -> Recommendation | None:
    """Подписки > 3000 руб/месяц при любом доходе."""
    subscriptions = agg.get("подписки") or 0
    if subscriptions < 3000:
        return None
    return Recommendation(
        text=f"Расходы на подписки: {int(subscriptions)} ₽ за последние 30 дней.",
        why="Регулярно пересматривайте подписки — многие забывают об отменённых или редко используемых сервисах.",
        metric="subscriptions_absolute",
    )


# Порядок правил задаёт приоритет; возвращаем до 3 рекомендаций
ALL_RULES = [
    rule_subscriptions_share_of_income,
    rule_fastfood_share_of_food,
    rule_expense_trend_increase,
    rule_subscriptions_high_absolute,
]
