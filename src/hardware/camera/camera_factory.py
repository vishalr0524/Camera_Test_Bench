"""
Camera factory for Camera Test Bench.
"""

from src.hardware.camera.basler import BaslerCamera


def get_camera_class(model_name: str):
    """Return the camera class for the given model name.

    Args:
        model_name: e.g. 'basler'

    Returns:
        Camera class (not instance)

    Raises:
        ValueError: If model is not recognised
    """
    model_mapping = {
        "basler": BaslerCamera,
    }

    if model_name.lower() in model_mapping:
        return model_mapping[model_name.lower()]

    raise ValueError(
        f"Camera model '{model_name}' not recognised. "
        f"Available: {list(model_mapping.keys())}"
    )
