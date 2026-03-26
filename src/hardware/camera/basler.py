"""
Basler camera implementation for Camera Test Bench.
"""

import time
import numpy as np
from typing import Optional, Dict, Any, Union
from pypylon import pylon

from src.hardware.camera.camera import BaseCamera
from src.utils import get_logger
from src.exceptions.camera_exceptions import (
    CameraConfigException,
    CameraCaptureException,
    CameraConnectionException,
    CameraTimeoutException,
)

logger = get_logger(__name__)


class BaslerCamera(BaseCamera):
    """Basler camera implementation."""

    camera_brand: str = "Basler"

    def __init__(self, camera_config: Union[Dict[str, Any], str], cam_id: str) -> None:
        """Initialize Basler camera.

        Args:
            camera_config: Configuration dict or path to config JSON file
            cam_id: Camera ID in the config (e.g. 'camera_01')
        """
        logger.info(f"Starting Basler camera initialization for ID: {cam_id}")

        super().__init__(cam_config=camera_config, cam_id=cam_id)

        self.camera: Optional[pylon.InstantCamera] = None
        self.converter: Optional[pylon.ImageFormatConverter] = None

        self._setup_converter()
        self.connect()

        logger.info(f"Basler camera {cam_id} ready")

    # ------------------------------------------------------------------ #
    # Setup helpers                                                        #
    # ------------------------------------------------------------------ #

    def _setup_converter(self) -> None:
        """Setup BGR8 image format converter."""
        try:
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            logger.debug(f"Image converter configured for camera {self.cam_id}")
        except Exception as e:
            raise CameraConfigException(f"Converter setup failed: {e}")

    # ------------------------------------------------------------------ #
    # Connection                                                           #
    # ------------------------------------------------------------------ #

    def connect(self) -> None:
        """Connect to the Basler camera by serial number."""
        try:
            tl_factory = pylon.TlFactory.GetInstance()
            devices = tl_factory.EnumerateDevices()

            if len(devices) == 0:
                raise CameraConnectionException("No Basler cameras found on system")

            serial_num = str(self.camera_config.get("serial_num", "")).strip()
            if not serial_num:
                raise CameraConfigException(f"No serial number configured for camera {self.cam_id}")

            target_device = None
            for device in devices:
                if device.GetSerialNumber() == serial_num:
                    target_device = device
                    break

            if target_device is None:
                available = [d.GetSerialNumber() for d in devices]
                raise CameraConnectionException(
                    f"Camera S/N '{serial_num}' not found. Available: {available}"
                )

            self.camera = pylon.InstantCamera(tl_factory.CreateDevice(target_device))
            self.camera.Open()

            if not self.is_open():
                raise CameraConnectionException("Failed to open camera connection")

            logger.info(
                f"Camera {self.cam_id} opened – "
                f"Model: {self.camera.GetDeviceInfo().GetModelName()}, "
                f"S/N: {self.camera.GetDeviceInfo().GetSerialNumber()}"
            )

            self._configure_camera()
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            self.status = True
            logger.info(f"Camera {self.cam_id} connected and grabbing")

        except Exception as e:
            self.status = False
            logger.error(f"Failed to connect camera {self.cam_id}: {e}", exc_info=True)
            raise

    def disconnect(self) -> None:
        """Disconnect from camera and release resources."""
        try:
            if self.camera and self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            if self.camera and self.camera.IsOpen():
                self.camera.Close()
            self.status = False
            logger.info(f"Camera {self.cam_id} disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting camera {self.cam_id}: {e}", exc_info=True)
            self.status = False

    def is_open(self) -> bool:
        """Return True if camera connection is open."""
        try:
            return self.camera is not None and self.camera.IsOpen()
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Configuration                                                        #
    # ------------------------------------------------------------------ #

    def _configure_camera(self) -> None:
        """Apply configuration parameters to the physical camera."""
        try:
            self.grab_timeout = self.camera_config.get("grab_timeout", 5000)

            trigger_mode = self.camera_config.get("trigger_mode", "software").lower()
            self.set_trigger(mode=trigger_mode)

            framerate = self.camera_config.get("framerate")
            if framerate:
                self.set_framerate(fps=framerate)

            exposure = self.camera_config.get("exposure")
            if exposure:
                self.set_exposure(exposure=exposure)

            self._set_optional_parameter("GainAuto", "gain_auto")
            self._set_optional_parameter("BalanceWhiteAuto", "balance_white_auto")

            logger.info(f"Camera {self.cam_id} configuration applied")

        except Exception as e:
            raise CameraConfigException(f"Camera configuration failed: {e}")

    def _set_optional_parameter(self, param_name: str, config_key: str) -> None:
        """Set an optional camera parameter, ignoring if unsupported."""
        try:
            value = self.camera_config.get(config_key)
            if value is not None:
                getattr(self.camera, param_name).Value = value
                logger.debug(f"Set {param_name}={value} for camera {self.cam_id}")
        except (pylon.LogicalErrorException, AttributeError):
            logger.debug(f"Camera {self.cam_id} does not support parameter: {param_name}")
        except Exception as e:
            logger.warning(f"Failed to set {param_name} for camera {self.cam_id}: {e}")

    # ------------------------------------------------------------------ #
    # Trigger                                                              #
    # ------------------------------------------------------------------ #

    def set_trigger(self, mode: str = "software") -> None:
        """Set camera trigger mode.

        Args:
            mode: 'software' or 'hardware'
        """
        try:
            if mode.lower() == "software":
                self.camera.TriggerMode.Value = "Off"
                self.trigger_mode = "software"
                logger.info(f"Software trigger set for camera {self.cam_id}")

            elif mode.lower() == "hardware":
                self.camera.TriggerMode.Value = "On"
                self.camera.TriggerSelector.Value = self.camera_config.get("trigger_selector", "FrameStart")
                self.camera.TriggerActivation.Value = self.camera_config.get("trigger_activation", "RisingEdge")
                self.camera.TriggerSource.Value = self.camera_config.get("trigger_source", "Line1")
                self.trigger_mode = "hardware"
                logger.info(
                    f"Hardware trigger set for camera {self.cam_id} "
                    f"(Source={self.camera_config.get('trigger_source', 'Line1')})"
                )
            else:
                raise CameraConfigException(f"Unknown trigger mode: {mode}. Use 'software' or 'hardware'.")

        except Exception as e:
            logger.error(f"Failed to set trigger mode for camera {self.cam_id}: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Framerate / Exposure                                                 #
    # ------------------------------------------------------------------ #

    def set_framerate(self, fps: float) -> None:
        """Set camera acquisition framerate."""
        if fps <= 0:
            raise CameraConfigException(f"Invalid framerate: {fps}")
        try:
            try:
                min_fps = self.camera.AcquisitionFrameRate.Min
                max_fps = self.camera.AcquisitionFrameRate.Max
                fps = max(min_fps, min(fps, max_fps))
                self.camera.AcquisitionFrameRate.Value = fps
            except pylon.LogicalErrorException:
                self.camera.AcquisitionFrameRateEnable.Value = True
                min_fps = self.camera.AcquisitionFrameRateAbs.Min
                max_fps = self.camera.AcquisitionFrameRateAbs.Max
                fps = max(min_fps, min(fps, max_fps))
                self.camera.AcquisitionFrameRateAbs.Value = fps
            logger.info(f"Framerate set to {fps} FPS for camera {self.cam_id}")
        except Exception as e:
            logger.error(f"Failed to set framerate for camera {self.cam_id}: {e}")
            raise

    def set_exposure(self, exposure: float) -> None:
        """Set camera exposure time in microseconds."""
        exposure = int(exposure)
        if exposure <= 0:
            raise CameraConfigException(f"Invalid exposure value: {exposure}")
        try:
            self.camera.ExposureAuto.Value = "Off"
            self.camera.ExposureMode.Value = "Timed"
            try:
                min_exp = self.camera.ExposureTime.Min
                max_exp = self.camera.ExposureTime.Max
                exposure = max(min_exp, min(exposure, max_exp))
                self.camera.ExposureTime.Value = exposure
            except pylon.LogicalErrorException:
                min_exp = self.camera.ExposureTimeAbs.Min
                max_exp = self.camera.ExposureTimeAbs.Max
                exposure = max(min_exp, min(exposure, max_exp))
                self.camera.ExposureTimeAbs.Value = exposure
            logger.info(f"Exposure set to {exposure} µs for camera {self.cam_id}")
        except Exception as e:
            logger.error(f"Failed to set exposure for camera {self.cam_id}: {e}", exc_info=True)
            raise

    def get_exposure(self) -> float:
        """Get current camera exposure time in microseconds."""
        try:
            try:
                return self.camera.ExposureTime.Value
            except pylon.LogicalErrorException:
                return self.camera.ExposureTimeAbs.Value
        except Exception as e:
            logger.error(f"Failed to get exposure for camera {self.cam_id}: {e}")
            raise

    # ------------------------------------------------------------------ #
    # Image Capture                                                        #
    # ------------------------------------------------------------------ #

    def grab_image(self) -> Optional[np.ndarray]:
        """Grab a single image from the camera.

        Returns:
            Image as numpy array (BGR), or None on failure/timeout.
        """
        if not self.camera or not self.camera.IsGrabbing():
            raise CameraCaptureException(f"Camera {self.cam_id} is not ready for capture")

        try:
            grab_result = self.camera.RetrieveResult(
                self.grab_timeout,
                pylon.TimeoutHandling_ThrowException
            )

            if grab_result.GrabSucceeded():
                image = self.converter.Convert(grab_result)
                self.captured_image = image.GetArray()
                grab_result.Release()
                logger.debug(
                    f"Image grabbed – shape: {self.captured_image.shape}, "
                    f"dtype: {self.captured_image.dtype}"
                )
                return self.captured_image
            else:
                err_code = grab_result.GetErrorCode()
                err_desc = grab_result.GetErrorDescription()
                logger.error(f"Grab failed – code: {err_code}, desc: {err_desc}")
                grab_result.Release()
                return None

        except pylon.TimeoutException:
            if getattr(self, 'trigger_mode', 'software') == "hardware":
                logger.debug(f"Waiting for hardware trigger on camera {self.cam_id}...")
            else:
                logger.warning(f"Image grab timeout on camera {self.cam_id}")
            return None

        except Exception as e:
            logger.error(f"Unexpected capture error on camera {self.cam_id}: {e}", exc_info=True)
            raise CameraCaptureException(f"Image capture error: {e}")

    def clear_buffer(self) -> None:
        """Discard all pending frames from the camera buffer."""
        if not self.camera or not self.camera.IsGrabbing():
            return
        frames_cleared = 0
        try:
            while frames_cleared < 100:
                grab_result = self.camera.RetrieveResult(10, pylon.TimeoutHandling_Return)
                if grab_result.IsValid() and grab_result.GrabSucceeded():
                    grab_result.Release()
                    frames_cleared += 1
                else:
                    break
            logger.debug(f"Buffer cleared: {frames_cleared} frames discarded for camera {self.cam_id}")
        except Exception as e:
            logger.error(f"Error clearing buffer for camera {self.cam_id}: {e}")
