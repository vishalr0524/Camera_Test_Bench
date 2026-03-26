"""
Camera-related exceptions for Camera Test Bench.
"""


class CameraException(Exception):
    """Base exception class for all camera-related errors."""

    def __init__(self, message: str = "Camera error occurred"):
        self.message = message
        super().__init__(self.message)


class CameraConfigException(CameraException):
    """Exception raised for camera configuration errors."""

    def __init__(self, message: str = "Camera configuration error"):
        super().__init__(message)


class CameraConnectionException(CameraException):
    """Exception raised for camera connection errors."""

    def __init__(self, message: str = "Camera connection error"):
        super().__init__(message)


class CameraCaptureException(CameraException):
    """Exception raised for camera capture errors."""

    def __init__(self, message: str = "Camera capture error"):
        super().__init__(message)


class CameraTimeoutException(CameraException):
    """Exception raised for camera timeout errors."""

    def __init__(self, message: str = "Camera timeout error"):
        super().__init__(message)
