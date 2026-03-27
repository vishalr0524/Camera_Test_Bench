"""
Camera Test Bench v2 — PyQt5 UI Entry Point
============================================
Run this to launch the graphical interface:

    python test_bench_app_v2.py

The original terminal mode is still available:
    python test_bench_app.py
"""

import sys
import os
import argparse

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.utils import setup_logging, get_logger
from src.ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Camera Test Bench v2 — PyQt5 GUI"
    )
    parser.add_argument(
        "--config",
        default="configs/system_config.json",
        help="Path to system configuration JSON",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging(log_dir="logs", log_level="INFO", app_name="CameraTestBench_v2")
    logger = get_logger(__name__)
    logger.info("Camera Test Bench v2 starting")

    args = parse_args()

    # Enable HiDPI scaling on Windows / Linux
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Camera Test Bench")
    app.setApplicationVersion("2.0")

    # Global font
    font = QFont("Segoe UI" if sys.platform == "win32" else "Ubuntu", 12)
    app.setFont(font)

    window = MainWindow(config_path=args.config)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
