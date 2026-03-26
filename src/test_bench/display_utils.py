"""
Display utilities for Camera Test Bench.

All text overlays, banners, and result annotations drawn onto
OpenCV frames live here so the main workflow stays clean.
"""

import cv2
import numpy as np
from typing import Optional, Tuple

# ------------------------------------------------------------------ #
# Colour palette (BGR)                                                #
# ------------------------------------------------------------------ #
COLOR_GREEN  = (0,   220,  80)
COLOR_RED    = (0,    50, 220)
COLOR_YELLOW = (0,   200, 220)
COLOR_WHITE  = (255, 255, 255)
COLOR_BLACK  = (0,     0,   0)
COLOR_BLUE   = (220,  80,   0)
COLOR_ORANGE = (0,   140, 255)

FONT       = cv2.FONT_HERSHEY_SIMPLEX
FONT_SMALL = 0.55
FONT_MED   = 0.75
FONT_LARGE = 1.0
THICKNESS  = 2


# ------------------------------------------------------------------ #
# Low-level helpers                                                   #
# ------------------------------------------------------------------ #

def _draw_banner(
    frame: np.ndarray,
    text: str,
    y_top: int,
    height: int,
    bg_color: Tuple[int, int, int],
    text_color: Tuple[int, int, int] = COLOR_WHITE,
    font_scale: float = FONT_MED,
) -> np.ndarray:
    """Draw a filled rectangle banner with centred text."""
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, y_top), (w, y_top + height), bg_color, -1)
    (tw, th), _ = cv2.getTextSize(text, FONT, font_scale, THICKNESS)
    tx = (w - tw) // 2
    ty = y_top + (height + th) // 2
    cv2.putText(frame, text, (tx, ty), FONT, font_scale, text_color, THICKNESS, cv2.LINE_AA)
    return frame


def _draw_text_block(
    frame: np.ndarray,
    lines: list,
    x: int,
    y_start: int,
    font_scale: float = FONT_SMALL,
    color: Tuple[int, int, int] = COLOR_WHITE,
    line_height: int = 26,
    shadow: bool = True,
) -> None:
    """Draw multiple lines of text with optional drop-shadow."""
    for i, line in enumerate(lines):
        y = y_start + i * line_height
        if shadow:
            cv2.putText(frame, line, (x + 1, y + 1), FONT, font_scale, COLOR_BLACK, THICKNESS, cv2.LINE_AA)
        cv2.putText(frame, line, (x, y), FONT, font_scale, color, 1, cv2.LINE_AA)


# ------------------------------------------------------------------ #
# Public overlay builders                                             #
# ------------------------------------------------------------------ #

def overlay_step_header(
    frame: np.ndarray,
    step_num: int,
    total_steps: int,
    title: str,
) -> np.ndarray:
    """Draw a top banner showing the current step."""
    frame = frame.copy()
    banner_text = f"  STEP {step_num}/{total_steps}  |  {title}"
    _draw_banner(frame, banner_text, y_top=0, height=38, bg_color=(40, 40, 40))
    return frame


def overlay_instruction(
    frame: np.ndarray,
    lines: list,
    key_hint: Optional[str] = None,
) -> np.ndarray:
    """Draw instruction text in the bottom portion of the frame."""
    frame = frame.copy()
    h, w = frame.shape[:2]

    # Semi-transparent dark bar at bottom
    bar_h = 36 + len(lines) * 28
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    _draw_text_block(frame, lines, x=14, y_start=h - bar_h + 22, color=COLOR_WHITE)

    if key_hint:
        (tw, _), _ = cv2.getTextSize(key_hint, FONT, FONT_SMALL, 1)
        cv2.putText(
            frame, key_hint,
            (w - tw - 12, h - 10),
            FONT, FONT_SMALL, COLOR_YELLOW, 1, cv2.LINE_AA
        )
    return frame


def overlay_live_stats(
    frame: np.ndarray,
    sharpness: float,
    mean_intensity: float,
    threshold: float = 50.0,
) -> np.ndarray:
    """Overlay sharpness and intensity stats on a live frame."""
    frame = frame.copy()
    sharp_color = COLOR_GREEN if sharpness >= threshold else COLOR_ORANGE
    lines = [
        f"Sharpness : {sharpness:7.1f}  (min {threshold:.0f})",
        f"Intensity : {mean_intensity:7.1f}",
    ]
    _draw_text_block(frame, lines, x=10, y_start=50, color=sharp_color)
    return frame


def overlay_capture_result(
    frame: np.ndarray,
    passed: bool,
    details: dict,
) -> np.ndarray:
    """Annotate a captured image with pass/fail verdict."""
    frame = frame.copy()
    h, w = frame.shape[:2]

    if passed:
        verdict_text = "CAPTURE OK"
        verdict_color = COLOR_GREEN
        border_color  = COLOR_GREEN
    else:
        verdict_text = "CAPTURE FAILED"
        verdict_color = COLOR_RED
        border_color  = COLOR_RED

    # Coloured border
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), border_color, 6)

    # Verdict banner
    _draw_banner(frame, verdict_text, y_top=42, height=46,
                 bg_color=border_color, font_scale=FONT_LARGE)

    # Details block
    info_lines = []
    if "resolution" in details:
        info_lines.append(f"Resolution : {details['resolution']}")
    if "sharpness" in details:
        info_lines.append(f"Sharpness  : {details['sharpness']}")
    if "mean_intensity" in details:
        info_lines.append(f"Intensity  : {details['mean_intensity']}")
    if "warning" in details:
        info_lines.append(f"WARN: {details['warning']}")
    if "error" in details:
        info_lines.append(f"ERR : {details['error']}")

    _draw_text_block(frame, info_lines, x=14, y_start=106, color=COLOR_WHITE, line_height=28)

    prompt = "Press ENTER to accept  |  R to retake  |  Q to quit"
    _draw_text_block(frame, [prompt], x=14, y_start=h - 22, color=COLOR_YELLOW)

    return frame


def overlay_aperture_step(
    frame: np.ndarray,
    step_name: str,
    step_index: int,
    total_steps: int,
    exposure_us: int,
    mean_intensity: float,
) -> np.ndarray:
    """Overlay aperture test step information on captured image."""
    frame = frame.copy()
    h, w = frame.shape[:2]

    title = f"APERTURE TEST  –  {step_name.upper()}  ({step_index}/{total_steps})"
    _draw_banner(frame, title, y_top=0, height=38, bg_color=(60, 30, 10))

    lines = [
        f"Exposure   : {exposure_us} µs",
        f"Mean Intensity : {mean_intensity:.1f} / 255",
    ]
    _draw_text_block(frame, lines, x=14, y_start=50, color=COLOR_WHITE, line_height=28)

    prompt = "Press ENTER to accept this step"
    _draw_text_block(frame, [prompt], x=14, y_start=h - 22, color=COLOR_YELLOW)
    return frame


def overlay_aperture_summary(
    frame: np.ndarray,
    passed: bool,
    intensities: dict,
    message: str,
) -> np.ndarray:
    """Show the final aperture trend pass/fail summary."""
    frame = frame.copy()
    h, w = frame.shape[:2]

    color = COLOR_GREEN if passed else COLOR_RED
    verdict = "APERTURE TREND PASS  ✓" if passed else "APERTURE TREND FAIL  ✗"
    _draw_banner(frame, verdict, y_top=0, height=44, bg_color=color)

    lines = [f"{k.upper():<10}: intensity = {v:.1f}" for k, v in intensities.items()]
    lines.append("")
    lines.append(message)
    _draw_text_block(frame, lines, x=14, y_start=56, color=COLOR_WHITE, line_height=28)

    prompt = "Press ENTER to continue"
    _draw_text_block(frame, [prompt], x=14, y_start=h - 22, color=COLOR_YELLOW)
    return frame


def overlay_hardware_trigger_wait(frame: np.ndarray) -> np.ndarray:
    """Overlay shown while waiting for hardware trigger."""
    frame = frame.copy()
    h, w = frame.shape[:2]
    _draw_banner(frame, "HARDWARE TRIGGER MODE – Waiting for signal…",
                 y_top=0, height=44, bg_color=(80, 0, 0))
    lines = [
        "Camera is now in HARDWARE TRIGGER mode.",
        "Press the push button connected to the trigger line.",
        "",
        "Press Q to abort.",
    ]
    _draw_text_block(frame, lines, x=14, y_start=60, color=COLOR_WHITE, line_height=30)
    return frame


def overlay_hardware_trigger_success(frame: np.ndarray) -> np.ndarray:
    """Overlay shown when hardware trigger image is captured."""
    frame = frame.copy()
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w - 1, h - 1), COLOR_GREEN, 8)
    _draw_banner(frame, "HARDWARE TRIGGER  –  IMAGE CAPTURED  ✓",
                 y_top=0, height=50, bg_color=COLOR_GREEN, text_color=COLOR_BLACK)
    prompt = "Press ENTER or Q to finish"
    _draw_text_block(frame, [prompt], x=14, y_start=h - 22, color=COLOR_YELLOW)
    return frame


def make_info_screen(
    title: str,
    lines: list,
    width: int = 900,
    height: int = 500,
    title_color: Tuple[int, int, int] = COLOR_BLUE,
) -> np.ndarray:
    """Create a plain dark information screen (no live feed required)."""
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (30, 30, 30)
    _draw_banner(canvas, title, y_top=0, height=52, bg_color=title_color)
    _draw_text_block(canvas, lines, x=30, y_start=80, line_height=32, color=COLOR_WHITE)
    return canvas
