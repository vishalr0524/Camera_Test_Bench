"""
Logging setup for Camera Test Bench.
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from typing import Union

_CONFIGURED = False
_LOGGING_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "logging_config.json"


def setup_logging(
    log_dir: Union[str, Path, None] = None,
    log_level: str = "INFO",
    app_name: str = "CameraTestBench",
    backup_days: int = 14,
) -> None:
    """Initialize logging to console and a daily-rotated file."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    project_root = Path(__file__).parents[2]

    if log_dir is None:
        log_dir_path = project_root / "logs"
    else:
        log_dir_path = project_root / log_dir
    log_dir_path.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    for h in root.handlers[:]:
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    logfile = log_dir_path / f"{app_name}.log"
    file_handler = TimedRotatingFileHandler(
        filename=str(logfile), when="midnight", backupCount=backup_days, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: Union[str, None] = None) -> logging.Logger:
    """Return a named logger. Bootstraps logging on first call."""
    global _CONFIGURED
    if not _CONFIGURED:
        try:
            from src.utils.config import read_config
            config = read_config(str(_LOGGING_CONFIG_PATH)).get("logging", {})
            setup_logging(
                log_dir=config.get("log_dir"),
                log_level=config.get("log_level", "INFO"),
                app_name=config.get("app_name", "CameraTestBench"),
                backup_days=config.get("backup_days", 14),
            )
        except Exception:
            logging.basicConfig(level=logging.INFO)
            setup_logging()

    if name is None:
        frame = sys._getframe(1)
        name = frame.f_globals.get("__name__", "root")
    return logging.getLogger(name)
