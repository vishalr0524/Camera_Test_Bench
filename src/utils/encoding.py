"""
Image encoding utilities for Camera Test Bench.
"""

import base64
import cv2
import numpy as np
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def encode_image_to_base64(image: np.ndarray, format: str = "png") -> str:
    """Convert numpy image array to base64 string.

    Args:
        image: numpy image array
        format: image encoding format ('jpg' or 'png')

    Returns:
        Base64 encoded image string
    """
    logger.debug("Encoding numpy array to base64 string")
    _, buffer = cv2.imencode(f".{format.lower()}", image)
    encoded_img = base64.b64encode(buffer).decode("utf-8")
    logger.debug("Successfully encoded image to base64")
    return encoded_img
