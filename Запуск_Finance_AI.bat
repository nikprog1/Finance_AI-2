@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Активируем venv, если он есть
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

REM Запуск приложения
python main.py 2>nul
if errorlevel 1 (
    py main.py 2>nul
)
if errorlevel 1 (
    echo Ошибка запуска. Убедитесь, что Python и зависимости установлены.
    echo Выполните: pip install -r requirements.txt requirements-llm.txt
    pause
)
