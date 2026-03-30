"""
Camera enumeration utilities for Camera Test Bench.

Change 5: GigE camera detection added.
Pylon's TlFactory.EnumerateDevices() already discovers GigE cameras
automatically when the network interface is reachable — including via
USB-C to Ethernet adapters or built-in Ethernet ports.

The only requirement is that Pylon's GigE Vision transport layer (pylon GigE TL)
is installed (it is included in the full Pylon installer) and that the OS has
assigned an IP address to the network interface the camera is connected to.

No code changes are needed to detect GigE vs USB3 cameras — Pylon handles
both through the same EnumerateDevices() call. The function now also logs
the device type (USB3 / GigE / other) for easier debugging.
"""

from pypylon import pylon
from src.utils import get_logger
from src.exceptions.camera_exceptions import CameraConnectionException

logger = get_logger(__name__)


def _device_type(device_info) -> str:
    """Return a short string describing the transport layer of a device."""
    try:
        tl = device_info.GetDeviceClass()          # e.g. "BaslerGigE", "BaslerUsb"
        if "gige" in tl.lower() or "gige" in device_info.GetModelName().lower():
            return "GigE"
        if "usb" in tl.lower():
            return "USB3"
        return tl
    except Exception:
        return "Unknown"


def get_available_cameras_basler() -> list:
    """Enumerate all real (non-emulated) Basler cameras on the system.

    Detects cameras connected via:
    - USB 3.0 (standard)
    - GigE (via built-in Ethernet port OR USB-C / USB-A to Ethernet adapter)

    Requirements for GigE detection:
    - Pylon full installer must be used (includes GigE TL)
    - The network adapter (USB-C dongle or built-in) must have a valid IP
    - Camera and PC must be on the same subnet (e.g. both 192.168.x.x)
    - Firewall must allow pylon GigE traffic (UDP broadcast on port 3956)

    Returns:
        List of serial number strings for all detected cameras.
    """
    try:
        logger.info("Enumerating available Basler cameras (USB3 + GigE) …")
        tl_factory = pylon.TlFactory.GetInstance()

        # EnumerateDevices() scans ALL installed transport layers in one call.
        # This includes BaslerUsb, BaslerGigE, BaslerCamEmu (emulator), etc.
        devices = tl_factory.EnumerateDevices()

        if len(devices) == 0:
            logger.warning("No Basler cameras found on system (USB3 or GigE)")
            return []

        camera_list = []
        for device in devices:
            model_name = device.GetModelName()

            # Skip software emulators
            if "emu" in model_name.lower():
                logger.info(f"Skipping emulated camera: {model_name}")
                continue

            serial_num  = device.GetSerialNumber()
            device_type = _device_type(device)
            camera_list.append(serial_num)
            logger.info(
                f"Found camera – S/N: {serial_num}, "
                f"Model: {model_name}, Interface: {device_type}"
            )

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
