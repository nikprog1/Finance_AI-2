"""
Настройка логирования Finance AI. Логи пишутся в файл и в консоль (если запуск из терминала).
"""
import logging
import sys
from pathlib import Path

from version import __version__

LOG_DIR = Path(r"Q:\bank_analyzer") if Path(r"Q:\bank_analyzer").exists() else Path.home() / ".bank_analyzer"
LOG_FILE = LOG_DIR / "finance_ai.log"
_actual_log_file: Path | None = None


def setup_logging(level: int = logging.DEBUG) -> None:
    """Настраивает логгер для приложения. Вызывать при старте main()."""
    log_dir = LOG_DIR
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_dir = Path.home() / ".bank_analyzer"
        log_dir.mkdir(parents=True, exist_ok=True)
    global _actual_log_file
    log_path = log_dir / "finance_ai.log"
    _actual_log_file = log_path

    formatter = logging.Formatter(
        f"%(asctime)s [%(levelname)s] v{__version__} %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Файл
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Консоль (если есть)
    if sys.stdout and hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root.addHandler(ch)


def get_log_path() -> Path:
    """Путь к файлу лога (после вызова setup_logging)."""
    return _actual_log_file if _actual_log_file is not None else LOG_FILE
