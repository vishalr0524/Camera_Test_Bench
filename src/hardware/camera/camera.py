"""
Base camera class for Camera Test Bench.
"""

import numpy as np
from typing import Optional, Dict, Any, Union

from src.utils import read_config, get_logger
from src.exceptions.camera_exceptions import CameraConfigException

logger = get_logger(__name__)


class BaseCamera:
    """Base camera class for single camera operations."""

    def __init__(self, cam_config: Union[Dict[str, Any], str], cam_id: str) -> None:
        """Initialize base camera.

        Args:
            cam_config: Camera configuration dictionary or path to config file
            cam_id: Camera ID to initialize
        """
        logger.info(f"Starting camera initialization for ID: {cam_id}")
        self.cam_id = cam_id

        # Load config from file if path is provided
        if isinstance(cam_config, str):
            logger.debug(f"Loading camera config from file: {cam_config}")
            try:
                cam_config = read_config(config_path=cam_config)
            except Exception as e:
                logger.error(f"Failed to load camera config from {cam_config}: {e}", exc_info=True)
                raise CameraConfigException(f"Config loading failed: {e}")

        # Validate configuration
        try:
            self.validate_camera_config(cam_config, self.cam_id)
        except Exception as e:
            logger.error(f"Camera config validation failed for ID {cam_id}: {e}", exc_info=True)
            raise CameraConfigException(f"Invalid configuration: {e}")

        self.status = False
        self.camera_config = cam_config["cameras"][self.cam_id]
        self.captured_image: Optional[np.ndarray] = None

        logger.info(f"Camera {self.cam_id} configuration loaded:")
        logger.info(f"  - Serial Number : {self.camera_config.get('serial_num', 'N/A')}")
        logger.info(f"  - Exposure      : {self.camera_config.get('exposure', 'N/A')}")
        logger.info(f"  - Trigger Mode  : {self.camera_config.get('trigger_mode', 'N/A')}")
        logger.info(f"  - Grab Timeout  : {self.camera_config.get('grab_timeout', 'N/A')}")
        logger.info(f"Camera {self.cam_id} base initialization completed")

    def validate_camera_config(self, config: Dict[str, Any], cam_id: str) -> None:
        """Validate camera configuration structure."""
        if "cameras" not in config:
            raise ValueError("Missing required config key: 'cameras'")

        if not isinstance(config["cameras"], dict):
            raise ValueError("'cameras' must be a dictionary")

        if cam_id not in config["cameras"]:
            available = list(config["cameras"].keys())
            raise ValueError(f"Camera ID '{cam_id}' not found. Available: {available}")

        cam_cfg = config["cameras"][cam_id]
        if "serial_num" not in cam_cfg:
            raise ValueError(f"Missing 'serial_num' for camera '{cam_id}'")

    # ------------------------------------------------------------------ #
    # Abstract interface – child classes must implement these             #
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        raise NotImplementedError("connect() must be implemented by child class")

    def disconnect(self) -> None:
        raise NotImplementedError("disconnect() must be implemented by child class")

    def is_open(self) -> bool:
        raise NotImplementedError("is_open() must be implemented by child class")

    def grab_image(self) -> Optional[np.ndarray]:
        raise NotImplementedError("grab_image() must be implemented by child class")

    def set_trigger(self, mode: str) -> None:
        raise NotImplementedError("set_trigger() must be implemented by child class")

    def set_framerate(self, fps: float) -> None:
        raise NotImplementedError("set_framerate() must be implemented by child class")

    def set_exposure(self, exposure: float) -> None:
        raise NotImplementedError("set_exposure() must be implemented by child class")

    # ------------------------------------------------------------------ #
    # Context manager                                                      #
    # ------------------------------------------------------------------ #

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'disconnect'):
            try:
                self.disconnect()
            except Exception as e:
                logger.error(f"Error during camera cleanup for {self.cam_id}: {e}", exc_info=True)
        if exc_type is not None:
            logger.error(f"Exception in camera context: {exc_type.__name__}: {exc_val}", exc_info=True)
        return False
