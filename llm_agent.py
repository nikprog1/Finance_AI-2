"""
Локальный LLM-агент для финансовых советов (Llama-3.1-8B-Instruct, GGUF).
Работает оффлайн через llama-cpp-python. Fallback на OpenAI API при OPENAI_API_KEY.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Опциональный импорт — приложение работает без llama-cpp-python
try:
    from llama_cpp import Llama
    _LLAMA_AVAILABLE = True
except ImportError:
    Llama = None
    _LLAMA_AVAILABLE = False

# Путь к модели по умолчанию
MODELS_DIR = Path.home() / ".bank_analyzer" / "models"
DEFAULT_MODEL_NAME = "llama-3.1-8b-instruct-q4_k_m.gguf"

SYSTEM_PROMPT = """Ты — финансовый консультант. Твоя задача — дать ОДИН краткий совет (1–2 предложения) на основе анонимизированных метрик.
Правила: не выдумывай числа; говори только о том, что явно следует из данных; не давай медицинских или юридических рекомендаций; пиши на русском."""

USER_PROMPT_TEMPLATE = """Ниже — агрегированные метрики пользователя за последние 30 дней (без личных данных):

{json_metrics}

Дай один конкретный совет по управлению финансами. Только текст совета, без преамбулы."""


def _generate_via_openai(metrics: dict[str, Any]) -> str | None:
    """Fallback на OpenAI API при наличии OPENAI_API_KEY. Возвращает совет или None."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        json_metrics = json.dumps(metrics, ensure_ascii=False, indent=2)
        user_content = USER_PROMPT_TEMPLATE.format(json_metrics=json_metrics)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=150,
            temperature=0.3,
        )
        text = (response.choices or [{}])[0].message.content
        return text.strip() if text else None
    except ImportError:
        logger.warning("openai не установлен; pip install openai")
        return None
    except Exception as e:
        logger.exception("Ошибка OpenAI API: %s", e)
        return None


def _build_prompt(metrics: dict[str, Any]) -> str:
    """Собирает промпт для Llama 3.1 Instruct (chat-формат)."""
    json_metrics = json.dumps(metrics, ensure_ascii=False, indent=2)
    user_part = USER_PROMPT_TEMPLATE.format(json_metrics=json_metrics)
    # Llama 3.1 chat format
    prompt = (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n\n"
        f"{SYSTEM_PROMPT}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_part}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    return prompt


def get_setup_instructions() -> str:
    """Инструкция по установке локальной модели для показа пользователю."""
    return (
        "Локальная модель не загружена.\n\n"
        "1. pip install -r requirements-llm.txt\n"
        f"2. Скачайте GGUF-модель (llama-3.1-8b-instruct) и поместите в:\n   {MODELS_DIR}\n"
        f"3. Имя файла: {DEFAULT_MODEL_NAME}\n\n"
        "Либо: pip install openai и задайте OPENAI_API_KEY для облачного совета."
    )


class LlamaAgent:
    """
    Обёртка над llama-cpp-python для генерации финансовых советов.
    Lazy init: модель загружается при первом вызове ensure_loaded() / generate_advice().
    """

    def __init__(self, model_path: str | Path | None = None):
        if model_path is None:
            model_path = MODELS_DIR / DEFAULT_MODEL_NAME
        self.model_path = Path(model_path)
        self._llama: Any = None
        self._load_attempted = False
        self._failure_reason: str = ""

    def ensure_loaded(self) -> bool:
        """
        Загружает модель при первом вызове. Возвращает True при успехе, False при ошибке.
        """
        if self._llama is not None:
            return True
        if self._load_attempted:
            return False
        self._load_attempted = True
        if not _LLAMA_AVAILABLE:
            self._failure_reason = "llama-cpp-python не установлен"
            logger.warning("llama-cpp-python не установлен; ИИ-совет недоступен.")
            return False
        if not self.model_path.is_file():
            self._failure_reason = f"Модель не найдена: {self.model_path}"
            logger.warning("Модель не найдена: %s", self.model_path)
            return False
        try:
            self._llama = Llama(
                model_path=str(self.model_path),
                n_ctx=2048,
                n_threads=2,
                verbose=False,
            )
            return True
        except Exception as e:
            self._failure_reason = str(e)
            logger.exception("Ошибка загрузки модели: %s", e)
            return False

    def get_failure_reason(self) -> str:
        """Причина, по которой модель недоступна (после неудачного ensure_loaded)."""
        return self._failure_reason or "Неизвестная ошибка"

    def generate_advice(self, metrics: dict[str, Any]) -> str | None:
        """
        Строит промпт из метрик, вызывает модель (локальная Llama или OpenAI), возвращает текст совета или None.
        """
        if self.ensure_loaded():
            prompt = _build_prompt(metrics)
            try:
                out = self._llama(
                    prompt,
                    max_tokens=150,
                    temperature=0.3,
                    stop=["<|eot_id|>", "\n\n"],
                    echo=False,
                )
                text = (out.get("choices") or [{}])[0].get("text", "").strip()
                return text if text else None
            except Exception as e:
                logger.exception("Ошибка генерации совета: %s", e)
                return None

        # Fallback на OpenAI API
        return _generate_via_openai(metrics)


# Синглтон для использования из financial_agent и main
_agent: LlamaAgent | None = None


def get_agent(model_path: str | Path | None = None) -> LlamaAgent:
    """Возвращает глобальный LlamaAgent (ленивая инициализация)."""
    global _agent
    if _agent is None:
        _agent = LlamaAgent(model_path=model_path)
    return _agent
