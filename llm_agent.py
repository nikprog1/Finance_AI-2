"""
Облачной LLM-агент для финансовых советов (OpenRouter / OpenAI-compatible API).
Работает через httpx, конфигурация из .env.
"""
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Конфигурация из .env
LLM_API_URL = os.environ.get(
    "LLM_API_URL",
    (os.environ.get("NEXT_PUBLIC_APP_URL") or "https://openrouter.ai/api/v1").rstrip("/") + "/chat/completions",
)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "z-ai/glm-4.5-air")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))

SYSTEM_PROMPT = """Ты — финансовый консультант. Твоя задача — дать ОДИН краткий совет (1–2 предложения) на основе анонимизированных метрик.
Правила: не выдумывай числа; говори только о том, что явно следует из данных; не давай медицинских или юридических рекомендаций; пиши на русском."""

USER_PROMPT_TEMPLATE = """Ниже — агрегированные метрики пользователя за последние 30 дней (без личных данных):

{json_metrics}

Дай один конкретный совет по управлению финансами. Только текст совета, без преамбулы."""

GOAL_SYSTEM_PROMPT = """Ты — мой финансовый консультант. Строгие правила: не упоминай конкретные бренды; не давай советов по инвестициям или кредитам; не придумывай данные — используй только те, что в метриках; пиши на русском; ответ должен быть ёмким."""

GOAL_USER_PROMPT_TEMPLATE = """Помоги достичь {target_amount} ₽ к {target_date}. Проанализируй мои траты.

КРИТИЧЕСКИ ВАЖНО: В ответе ОБЯЗАТЕЛЬНО включи фразу: «Для достижения цели к {target_date} необходимо откладывать {monthly_savings_rub} ₽ в месяц.» — используй ТОЧНО target_date и monthly_savings_rub из метрик (не вычисляй сумму сам).

Дату покажи в формате ДД.ММ.ГГГГ (например 11.03.2027).

Дополнительно: рекомендации, как сократить расходы. Ответ ёмкий. Не упоминай данные, которых нет.

Метрики (анонимизированные):
{json_metrics}"""


def get_setup_instructions() -> str:
    """Инструкция по настройке Cloud API для показа пользователю."""
    return (
        "Облачный LLM не настроен.\n\n"
        "Добавьте в .env или .env.local:\n"
        "  LLM_API_KEY=sk-your-key\n"
        "  LLM_API_URL=https://openrouter.ai/api/v1/chat/completions\n"
        "  LLM_MODEL=openai/gpt-4o-mini\n\n"
        "Ключ: https://openrouter.ai/keys или https://platform.openai.com/api-keys"
    )


class CloudAgent:
    """
    Агент для генерации финансовых советов через облачный API (OpenAI-совместимый).
    """

    def __init__(self):
        self._failure_reason: str = ""

    def get_failure_reason(self) -> str:
        """Причина последней ошибки."""
        return self._failure_reason or "Неизвестная ошибка"

    def generate_advice(self, metrics: dict[str, Any]) -> str | None:
        """
        Формирует промпт из метрик, отправляет запрос к API, возвращает текст совета или None.
        """
        api_key = (LLM_API_KEY or "").strip()
        if not api_key:
            self._failure_reason = "API-ключ не найден. Задайте LLM_API_KEY или OPENROUTER_API_KEY в .env"
            logger.warning(self._failure_reason)
            return None

        json_metrics = json.dumps(metrics, ensure_ascii=False, indent=2)
        user_content = USER_PROMPT_TEMPLATE.format(json_metrics=json_metrics)

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 80,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.debug("Отправка запроса к %s, модель %s", LLM_API_URL, LLM_MODEL)
            with httpx.Client(timeout=LLM_TIMEOUT) as client:
                response = client.post(LLM_API_URL, headers=headers, json=payload)

            # Обработка HTTP-ошибок до raise_for_status
            if response.status_code == 402:
                self._failure_reason = "Недостаточно кредитов. Проверьте баланс на https://openrouter.ai/settings/credits"
                logger.warning(self._failure_reason)
                return None

            if response.status_code == 404:
                try:
                    err = response.json()
                    msg = err.get("error", {}).get("message", "")
                except Exception:
                    msg = response.text[:200]
                self._failure_reason = f"Модель не найдена: {LLM_MODEL}. {msg}"
                logger.warning(self._failure_reason)
                return None

            if response.status_code == 400:
                try:
                    err = response.json()
                    msg = err.get("error", {}).get("message", response.text[:200])
                except Exception:
                    msg = response.text[:200]
                self._failure_reason = f"Неверный запрос: {msg}"
                logger.warning(self._failure_reason)
                return None

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "")
                extra = f" Подождите {retry_after} сек." if retry_after else ""
                self._failure_reason = f"Слишком много запросов (rate limit).{extra}"
                logger.warning(self._failure_reason)
                return None

            response.raise_for_status()
            data = response.json()

            text = ""
            if "choices" in data and data["choices"]:
                text = (data["choices"][0].get("message", {}).get("content") or "").strip()

            if text:
                logger.info("Cloud API: совет получен, %d символов", len(text))
                self._failure_reason = ""
                return text
            self._failure_reason = "Пустой ответ от API"
            return None

        except httpx.TimeoutException:
            self._failure_reason = f"Таймаут запроса ({LLM_TIMEOUT} сек)"
            logger.warning(self._failure_reason)
            return None
        except httpx.HTTPStatusError as e:
            err_text = e.response.text[:300] if e.response else str(e)
            self._failure_reason = f"HTTP {e.response.status_code}: {err_text}"
            logger.exception("HTTP ошибка: %s", e)
            return None
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            self._failure_reason = f"Нет подключения к интернету: {e}"
            logger.warning(self._failure_reason)
            return None
        except Exception as e:
            self._failure_reason = str(e)
            logger.exception("Ошибка Cloud API: %s", e)
            return None

    def generate_goal_advice(self, metrics: dict[str, Any]) -> str | None:
        """
        Генерация рекомендаций по финансовой цели. Строгий промпт: без брендов, инвестиций, галлюцинаций.
        При сетевой ошибке возвращает None (caller использует rule-based).
        """
        api_key = (LLM_API_KEY or "").strip()
        if not api_key:
            self._failure_reason = "API-ключ не найден. Задайте LLM_API_KEY или OPENROUTER_API_KEY в .env"
            logger.warning(self._failure_reason)
            return None

        json_metrics = json.dumps(metrics, ensure_ascii=False, indent=2)
        target_date = metrics.get("target_date", "")
        target_date_display = target_date  # DD.MM.YYYY при необходимости
        if len(target_date) >= 10 and target_date[4] == "-":
            try:
                from datetime import datetime
                dt = datetime.strptime(target_date[:10], "%Y-%m-%d")
                target_date_display = dt.strftime("%d.%m.%Y")
            except ValueError:
                pass
        user_content = GOAL_USER_PROMPT_TEMPLATE.format(
            target_amount=int(metrics.get("target_amount", 0)),
            target_date=target_date_display,
            monthly_savings_rub=int(metrics.get("monthly_savings_rub", 0)),
            json_metrics=json_metrics,
        )

        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": GOAL_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 300,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.debug("Отправка goal-запроса к %s", LLM_API_URL)
            with httpx.Client(timeout=LLM_TIMEOUT) as client:
                response = client.post(LLM_API_URL, headers=headers, json=payload)

            if response.status_code == 402:
                self._failure_reason = "Недостаточно кредитов"
                return None
            if response.status_code == 404:
                self._failure_reason = f"Модель не найдена: {LLM_MODEL}"
                return None
            if response.status_code in (400, 429):
                self._failure_reason = f"HTTP {response.status_code}"
                return None

            response.raise_for_status()
            data = response.json()
            text = ""
            if "choices" in data and data["choices"]:
                text = (data["choices"][0].get("message", {}).get("content") or "").strip()
            if text:
                logger.info("Cloud API: goal-совет получен, %d символов", len(text))
                self._failure_reason = ""
                return text
            self._failure_reason = "Пустой ответ от API"
            return None

        except (httpx.ConnectError, httpx.ConnectTimeout):
            self._failure_reason = "Нет подключения к интернету"
            logger.warning(self._failure_reason)
            return None
        except (httpx.TimeoutException, httpx.HTTPStatusError, Exception) as e:
            self._failure_reason = str(e)
            logger.exception("Ошибка goal API: %s", e)
            return None


# Синглтон для main и financial_agent
_agent: CloudAgent | None = None


def get_agent(model_path: str | None = None) -> CloudAgent:
    """Возвращает глобальный CloudAgent (ленивая инициализация). Параметр model_path игнорируется для совместимости."""
    global _agent
    if _agent is None:
        _agent = CloudAgent()
    return _agent
