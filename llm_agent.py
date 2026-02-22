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

EXPENSE_ADVICE_USER_PROMPT = """Ниже — агрегированные метрики пользователя (без личных данных):

{json_metrics}

В ответе ОБЯЗАТЕЛЬНО включи фразу: как сократить расходы. Ответ ёмкий. Не упоминай данные, которых нет."""


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

    def generate_expense_advice(
        self, metrics: dict[str, Any], api_config: dict[str, Any] | None = None
    ) -> str | None:
        """
        Генерация рекомендаций «как сократить расходы». Строгий промпт: без брендов, инвестиций.
        api_config: опционально из БД — api_url, api_key, model, timeout. Иначе — из .env.
        При сетевой ошибке возвращает None (caller использует rule-based).
        """
        if api_config:
            api_key = (api_config.get("api_key") or "").strip()
            api_url = api_config.get("api_url") or LLM_API_URL
            model = api_config.get("model") or LLM_MODEL
            timeout = int(api_config.get("timeout") or LLM_TIMEOUT)
        else:
            api_key = (LLM_API_KEY or os.environ.get("OPENROUTER_API_KEY", "") or "").strip()
            api_url = LLM_API_URL
            model = LLM_MODEL
            timeout = LLM_TIMEOUT
        if not api_key:
            self._failure_reason = "API-ключ не найден. Добавьте модель в Настройках или задайте LLM_API_KEY в .env"
            logger.warning(self._failure_reason)
            return None

        json_metrics = json.dumps(metrics, ensure_ascii=False, indent=2)
        user_content = EXPENSE_ADVICE_USER_PROMPT.format(json_metrics=json_metrics)

        payload = {
            "model": model,
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
            logger.debug("Отправка expense-advice запроса к %s", api_url)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(api_url, headers=headers, json=payload)

            if response.status_code == 402:
                self._failure_reason = "Недостаточно кредитов"
                return None
            if response.status_code == 404:
                self._failure_reason = f"Модель не найдена: {model}"
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
                logger.info("Cloud API: совет получен, %d символов", len(text))
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
            logger.exception("Ошибка expense-advice API: %s", e)
            return None


# Синглтон для main и financial_agent
_agent: CloudAgent | None = None


def get_agent(model_path: str | None = None) -> CloudAgent:
    """Возвращает глобальный CloudAgent (ленивая инициализация). Параметр model_path игнорируется для совместимости."""
    global _agent
    if _agent is None:
        _agent = CloudAgent()
    return _agent
