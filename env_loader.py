"""
Загрузка переменных окружения из .env файлов.
Приоритет: .env.local в директории проекта > .env в директории проекта.
"""
import os
import sys

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _get_base_path() -> str:
    """Путь к директории приложения (проекта или EXE)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_env() -> None:
    """Загрузить .env.local и .env. Вызывать при старте приложения."""
    if load_dotenv is None:
        return
    base = _get_base_path()
    for name in (".env.local", ".env"):
        path = os.path.join(base, name)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            load_dotenv(path, override=True)
            return
    load_dotenv()
