"""
Test result persistence for Camera Test Bench.

Saves captured images and a JSON test report to the results/ directory.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import cv2
import numpy as np

from src.utils import get_logger

logger = get_logger(__name__)


class ResultSaver:
    """Saves images and a structured test report for one test session."""

    def __init__(self, results_dir: str = "results", serial_num: str = "unknown") -> None:
        """Create a timestamped sub-directory for this test run.

        Args:
            results_dir: Base directory for all results
            serial_num: Camera serial number (used in folder name)
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = Path(results_dir) / f"{serial_num}_{ts}"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.report: Dict[str, Any] = {
            "serial_num": serial_num,
            "timestamp": ts,
            "steps": {},
        }
        logger.info(f"Result session directory: {self.session_dir}")

    # ------------------------------------------------------------------ #
    # Image saving                                                         #
    # ------------------------------------------------------------------ #

    def save_image(self, image: np.ndarray, name: str) -> str:
        """Save a numpy image to the session directory.

        Args:
            image: BGR numpy array
            name: Base filename (without extension)

        Returns:
            Full path to the saved file
        """
        if image is None:
            logger.warning(f"Skipping save for '{name}' – image is None")
            return ""

        filepath = str(self.session_dir / f"{name}.png")
        cv2.imwrite(filepath, image)
        logger.info(f"Image saved: {filepath}")
        return filepath

    # ------------------------------------------------------------------ #
    # Report helpers                                                       #
    # ------------------------------------------------------------------ #

    def record_step(self, step_name: str, data: Dict[str, Any]) -> None:
        """Record a step result in the in-memory report.

        Args:
            step_name: Human-readable step identifier
            data: Arbitrary dict of result data
        """
        self.report["steps"][step_name] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            **data,
        }
        logger.debug(f"Step recorded: {step_name} → {data}")

    def save_report(self) -> str:
        """Write the JSON test report to disk.

        Returns:
            Path to the saved report file.
        """
        self.report["completed_at"] = datetime.now().isoformat(timespec="seconds")

        # Compute overall pass/fail
        step_results = [
            v.get("passed", True)
            for v in self.report["steps"].values()
            if isinstance(v, dict) and "passed" in v
        ]
        self.report["overall_passed"] = all(step_results) if step_results else False

        report_path = str(self.session_dir / "test_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(self.report, f, indent=4)

        logger.info(f"Test report saved: {report_path}")
        return report_path
