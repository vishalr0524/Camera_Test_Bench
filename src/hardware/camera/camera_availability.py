"""
Camera enumeration utilities for Camera Test Bench.
"""

from pypylon import pylon
from src.utils import get_logger
from src.exceptions.camera_exceptions import CameraConnectionException

logger = get_logger(__name__)


def get_available_cameras_basler() -> list:
    """Enumerate all real (non-emulated) Basler cameras on the system.

    Returns:
        List of serial number strings.
    """
    try:
        logger.info("Enumerating available Basler cameras")
        tl_factory = pylon.TlFactory.GetInstance()
        devices = tl_factory.EnumerateDevices()

        if len(devices) == 0:
            logger.warning("No Basler cameras found on system")
            return []

        camera_list = []
        for device in devices:
            model_name = device.GetModelName()
            if "emu" in model_name.lower():
                logger.info(f"Skipping emulated camera: {model_name}")
                continue
            serial_num = device.GetSerialNumber()
            camera_list.append(serial_num)
            logger.info(f"Found – S/N: {serial_num}, Model: {model_name}")

        logger.info(f"Total Basler cameras found: {len(camera_list)}")
        return camera_list

    except Exception as e:
        logger.error(f"Failed to enumerate Basler cameras: {e}", exc_info=True)
        raise CameraConnectionException(f"Camera enumeration failed: {e}")


def get_available_cameras(model: str) -> list:
    """Get available cameras for the specified brand.

    Args:
        model: Camera brand identifier (e.g. 'basler')

    Returns:
        List of serial number strings.
    """
    if model.lower() == "basler":
        return get_available_cameras_basler()
    else:
        raise ValueError(f"Unsupported camera model: {model}")
