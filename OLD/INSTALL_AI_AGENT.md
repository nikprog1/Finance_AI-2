# Настройка AI-агента (облачный API)

Пошаговый порядок действий для включения блока «Сгенерировано ИИ» в Finance AI через облачный API (OpenRouter / OpenAI-совместимый).

---

## Шаг 1. Установить зависимости

```powershell
pip install -r requirements.txt
```

Основные зависимости для LLM уже включены: `httpx`, `python-dotenv`.

---

## Шаг 2. Создать .env.local

Скопируйте `.env.example` в `.env.local`:

```powershell
Copy-Item .env.example .env.local
```

Откройте `.env.local` и укажите API-ключ:

```env
LLM_API_KEY=sk-ваш-ключ
LLM_API_URL=https://openrouter.ai/api/v1/chat/completions
LLM_MODEL=openai/gpt-4o-mini
LLM_TIMEOUT=60
```

**Получить ключ:**
- OpenRouter (доступ к разным моделям): https://openrouter.ai/keys
- OpenAI: https://platform.openai.com/api-keys

**Совместимость:** можно использовать `OPENROUTER_API_KEY` вместо `LLM_API_KEY`.

---

## Шаг 3. Проверить настройку

Убедитесь, что в `.env.local` задан `LLM_API_KEY` (или `OPENROUTER_API_KEY`). Приложение загружает `.env.local` при старте.

---

## Шаг 4. Запустить приложение

Запустите Finance AI (ярлык или `Запуск_Finance_AI.bat`). Загрузите CSV с транзакциями и нажмите **«Запросить совет ИИ»**. Ответ приходит обычно за 2–10 секунд.

---

## Переменные окружения (.env.example)

| Переменная      | Описание                         | По умолчанию                                      |
|-----------------|----------------------------------|---------------------------------------------------|
| `LLM_API_KEY`   | API-ключ (или `OPENROUTER_API_KEY`) | —                                                 |
| `LLM_API_URL`   | URL chat completions API         | `https://openrouter.ai/api/v1/chat/completions`   |
| `LLM_MODEL`     | ID модели                        | `openai/gpt-4o-mini`                              |
| `LLM_TIMEOUT`   | Таймаут запроса (сек)            | `60`                                              |

---

## Логи

При ошибках детали пишутся в: `Q:\bank_analyzer\finance_ai.log` (или `%USERPROFILE%\.bank_analyzer\finance_ai.log`). Путь также показывается в блоке ИИ при ошибке.

---

## Устранение неполадок

| Проблема                    | Решение                                                                 |
|-----------------------------|-------------------------------------------------------------------------|
| «API-ключ не найден»        | Проверьте, что в `.env.local` задан `LLM_API_KEY` или `OPENROUTER_API_KEY`. |
| «Недостаточно кредитов» (402) | Проверьте баланс на https://openrouter.ai/settings/credits             |
| «Модель не найдена» (404)   | Проверьте `LLM_MODEL` на https://openrouter.ai/models                  |
| «Слишком много запросов» (429) | Подождите несколько секунд, уменьшите частоту запросов                 |
| Таймаут                     | Увеличьте `LLM_TIMEOUT` в `.env.local`                                 |
