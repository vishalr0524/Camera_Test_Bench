"""
Camera Test Bench – Entry Point
================================
Run this script to start the interactive test bench:

    python test_bench_app.py
    python test_bench_app.py --config configs/system_config.json

The application guides an operator through nine sequential steps:
  1. Serial number input & USB validation
  2. Live feed display
  3. Focus adjustment
  4. Spacebar capture
  5. Captured image confirmation
  6. Aperture adjustment at low / correct / high settings
  7. Switch to hardware trigger mode
  8. Press push button to trigger
  9. Display hardware-triggered image
"""

import sys
import os
import argparse

# Ensure the project root is on the Python path regardless of where the
# script is launched from.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils import setup_logging, get_logger
from src.test_bench.workflow import TestBenchWorkflow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Camera Test Bench – interactive operator workflow"
    )
    parser.add_argument(
        "--config",
        default="configs/system_config.json",
        help="Path to system configuration JSON (default: configs/system_config.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Initialise logging early so all modules can log from startup.
    setup_logging(
        log_dir="logs",
        log_level="INFO",
        app_name="CameraTestBench",
    )
    logger = get_logger(__name__)
    logger.info("Camera Test Bench starting")

    try:
        bench = TestBenchWorkflow(config_path=args.config)
        bench.run()
    except KeyboardInterrupt:
        print("\n[Test Bench] Interrupted by user (Ctrl+C). Exiting.")
        logger.info("Test bench interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n[FATAL] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
