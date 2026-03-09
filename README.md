# Finance AI

Десктопное Windows-приложение для учёта личных финансов: импорт банковских CSV-выписок, управление транзакциями, отчёты по категориям и картам, финансовые цели и краткие рекомендации от облачного ИИ.

## Ссылки

- **Последний релиз:** [GitHub Releases](https://github.com/nikprog1/Finance_AI-2/releases/latest)
- **Лендинг:** [GitHub Pages](https://nikprog1.github.io/Finance_AI-2/)
- **Исходный код:** [github.com/nikprog1/Finance_AI-2](https://github.com/nikprog1/Finance_AI-2)
- **Инструкция по публикации:** [`docs/PUBLISH.md`](docs/PUBLISH.md)

## Возможности

- импорт CSV-выписок и защита от дублей;
- просмотр, поиск, фильтрация и редактирование транзакций;
- ручное добавление и удаление транзакций;
- отчёты по категориям, типам счёта, периодам и накоплениям;
- финансовые цели с прогрессом и расчётом требуемой суммы в месяц;
- отдельный ИИ-анализ расходов;
- отдельный ИИ-анализ всех финансовых целей сразу;
- сборка в `EXE` и установщик для Windows.

## Технологии

- `Python`
- `PyQt5`
- `SQLite`
- `matplotlib`
- `httpx`
- `PyInstaller`
- `Inno Setup`

## Требования

- Windows
- Python `3.14`
- PowerShell
- установленный Inno Setup Compiler для сборки установщика

## Быстрый запуск из исходников

```powershell
Set-Location "C:\Work\Finance_AI-2"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\main.py
```

## Сборка EXE

```powershell
Set-Location "C:\Work\Finance_AI-2"
.\.venv\Scripts\Activate.ps1
pyinstaller --clean .\Finance_AI.spec
```

Результат сборки:

- `dist\Finance_AI_1.0.0.exe`

## Сборка установщика

1. Откройте `Finance_AI_Setup.iss` в Inno Setup Compiler.
2. Нажмите `Build -> Compile`.

Результат сборки:

- `Output\Finance_AI_1.0.0_Setup.exe`

## Публикация релиза

1. Обновите версию в [`version.py`](version.py).
2. Пересоберите `EXE` через `PyInstaller`.
3. Пересоберите установщик через Inno Setup.
4. Создайте git-тег версии:

```powershell
Set-Location "C:\Work\Finance_AI-2"
git tag v1.0.0
git push origin v1.0.0
```

5. Откройте GitHub Releases и создайте релиз:
   - прикрепите `Finance_AI_1.0.0_Setup.exe`;
   - при необходимости прикрепите `Finance_AI_1.0.0.exe`.

## GitHub Pages

Лендинг находится в [`docs/index.html`](docs/index.html). Для публикации Pages:

1. Откройте `Settings -> Pages`.
2. Выберите `Deploy from a branch`.
3. Укажите ветку `main` и папку `/docs`.

## Текущая версия

- `1.0.0`

## Примечания для публикации

- В `Finance_AI.spec` уже включён `CSV_test.csv`.
- В `Finance_AI_Setup.iss` уже добавлен `CSV_test.csv` рядом с `EXE`.
- Перед публикацией проверьте совпадение версии в `version.py`, `Finance_AI_Setup.iss` и именах release-артефактов.
