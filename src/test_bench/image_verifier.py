"""
Image verification utilities for Camera Test Bench.

Provides sharpness analysis and intensity checks used during
the test bench workflow steps.
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Any
from src.utils import get_logger

logger = get_logger(__name__)


def compute_sharpness(image: np.ndarray) -> float:
    """Compute image sharpness using the Laplacian variance method.

    A higher value means a sharper image.

    Args:
        image: BGR or grayscale numpy array

    Returns:
        Variance of Laplacian (sharpness score)
    """
    if image is None or image.size == 0:
        return 0.0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    logger.debug(f"Computed sharpness score: {sharpness:.2f}")
    return float(sharpness)


def compute_mean_intensity(image: np.ndarray) -> float:
    """Compute mean pixel intensity of an image.

    Args:
        image: BGR or grayscale numpy array

    Returns:
        Mean intensity value in range [0, 255]
    """
    if image is None or image.size == 0:
        return 0.0

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    mean_val = float(np.mean(gray))
    logger.debug(f"Computed mean intensity: {mean_val:.2f}")
    return mean_val


def verify_capture(image: np.ndarray, sharpness_threshold: float = 50.0) -> Tuple[bool, Dict[str, Any]]:
    """Verify that a captured image is valid (not blank, not pure noise).

    Args:
        image: Captured BGR image
        sharpness_threshold: Minimum Laplacian variance to consider image in focus

    Returns:
        Tuple of (is_valid, details_dict)
    """
    details: Dict[str, Any] = {}

    if image is None or image.size == 0:
        details["error"] = "Image is None or empty"
        logger.warning("Capture verification failed: image is None or empty")
        return False, details

    h, w = image.shape[:2]
    details["resolution"] = f"{w} x {h}"

    sharpness = compute_sharpness(image)
    details["sharpness"] = round(sharpness, 2)
    details["sharpness_threshold"] = sharpness_threshold

    mean_intensity = compute_mean_intensity(image)
    details["mean_intensity"] = round(mean_intensity, 2)

    # Reject completely black or completely saturated images
    if mean_intensity < 5.0:
        details["error"] = "Image is completely black (underexposed or no signal)"
        logger.warning(f"Capture verification failed: mean intensity too low ({mean_intensity:.1f})")
        return False, details

    if mean_intensity > 250.0:
        details["error"] = "Image is completely white (overexposed)"
        logger.warning(f"Capture verification failed: mean intensity too high ({mean_intensity:.1f})")
        return False, details

    if sharpness < sharpness_threshold:
        details["warning"] = (
            f"Image may be out of focus (sharpness={sharpness:.1f}, "
            f"threshold={sharpness_threshold})"
        )
        logger.warning(details["warning"])
        # Return True with a warning — operator can still accept it
        details["is_focused"] = False
    else:
        details["is_focused"] = True

    logger.info(
        f"Capture verification passed – "
        f"resolution={details['resolution']}, "
        f"sharpness={sharpness:.1f}, "
        f"mean_intensity={mean_intensity:.1f}"
    )
    return True, details


def verify_aperture_sequence(
    intensities: Dict[str, float],
    expected_order: list = None,
) -> Tuple[bool, str]:
    """Verify that aperture images show the expected intensity trend.

    For a Basler camera, adjusting aperture changes brightness:
      low aperture  → less light → lower intensity
      correct       → nominal
      high aperture → more light → higher intensity

    Args:
        intensities: Dict mapping step name to mean intensity value.
                     e.g. {'low': 45.2, 'correct': 112.5, 'high': 198.7}
        expected_order: Ordered list of step keys from darkest to brightest.
                        Defaults to ['low', 'correct', 'high'].

    Returns:
        Tuple of (passed, message)
    """
    if expected_order is None:
        expected_order = ["low", "correct", "high"]

    missing = [s for s in expected_order if s not in intensities]
    if missing:
        return False, f"Missing intensity data for steps: {missing}"

    values = [intensities[s] for s in expected_order]

    # Check strictly increasing trend
    is_increasing = all(values[i] < values[i + 1] for i in range(len(values) - 1))

    if is_increasing:
        msg = (
            f"Aperture intensity trend PASSED ✓ – "
            + ", ".join(f"{s}={intensities[s]:.1f}" for s in expected_order)
        )
        logger.info(msg)
        return True, msg
    else:
        msg = (
            f"Aperture intensity trend FAILED ✗ – expected increasing values but got: "
            + ", ".join(f"{s}={intensities[s]:.1f}" for s in expected_order)
        )
        logger.warning(msg)
        return False, msg
