"""
Reusable PyQt5 widgets for Camera Test Bench v2 UI.
"""

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen
from PyQt5.QtWidgets import (
    QLabel, QWidget, QVBoxLayout, QHBoxLayout,
    QProgressBar, QFrame, QSizePolicy,
)


# ------------------------------------------------------------------ #
# Colour palette                                                      #
# ------------------------------------------------------------------ #
CLR_BG          = "#1a1a2e"
CLR_PANEL       = "#16213e"
CLR_ACCENT      = "#0f3460"
CLR_PRIMARY     = "#e94560"
CLR_SUCCESS     = "#2ecc71"
CLR_WARNING     = "#f39c12"
CLR_TEXT        = "#eaeaea"
CLR_TEXT_MUTED  = "#8899aa"
CLR_BORDER      = "#0f3460"


def make_label(text: str, size: int = 13, bold: bool = False,
               color: str = CLR_TEXT) -> QLabel:
    """Convenience factory for styled QLabels."""
    lbl = QLabel(text)
    font = QFont("Segoe UI" if __import__("sys").platform == "win32" else "Ubuntu", size)
    font.setBold(bold)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl


# ------------------------------------------------------------------ #
# CameraFeedWidget                                                    #
# ------------------------------------------------------------------ #

class CameraFeedWidget(QLabel):
    """Displays a live or static BGR numpy image, scaled to fit."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            f"background: #0a0a14; border: 2px solid {CLR_BORDER}; border-radius: 8px;"
        )
        self._show_placeholder()

    def _show_placeholder(self):
        placeholder = np.zeros((400, 640, 3), dtype=np.uint8)
        placeholder[:] = (20, 20, 30)
        cv2.putText(
            placeholder, "No Feed", (220, 210),
            cv2.FONT_HERSHEY_SIMPLEX, 1.4, (60, 60, 80), 2
        )
        self.update_frame(placeholder)

    def update_frame(self, frame: np.ndarray) -> None:
        """Accept a BGR numpy array and render it into the label."""
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix  = QPixmap.fromImage(qimg)
        self.setPixmap(
            pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )


# ------------------------------------------------------------------ #
# StepProgressWidget                                                  #
# ------------------------------------------------------------------ #

class StepProgressWidget(QWidget):
    """Horizontal row of numbered step circles."""

    STEP_LABELS = [
        "1\nSerial",
        "2\nLive Feed",
        "3\nFocus",
        "4\nCapture",
        "5\nConfirm",
        "6\nAperture",
        "7\nHW Trigger",
        "8\nButton",
        "9\nResult",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_step = 0
        self.setFixedHeight(80)
        self.setStyleSheet("background: transparent;")

    def set_step(self, step: int) -> None:
        self.current_step = step
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        n     = len(self.STEP_LABELS)
        w     = self.width()
        h     = self.height()
        r     = 18                          # circle radius
        gap   = (w - 2 * r) / (n - 1)

        font_small = QFont("Segoe UI", 7)
        font_num   = QFont("Segoe UI", 9, QFont.Bold)

        for i, label in enumerate(self.STEP_LABELS):
            cx = int(r + i * gap)
            cy = 22

            # connector line
            if i > 0:
                prev_cx = int(r + (i - 1) * gap)
                if i < self.current_step:
                    painter.setPen(QPen(QColor(CLR_SUCCESS), 2))
                else:
                    painter.setPen(QPen(QColor(CLR_BORDER), 2))
                painter.drawLine(prev_cx + r, cy, cx - r, cy)

            # circle fill
            if i + 1 < self.current_step:
                fill = QColor(CLR_SUCCESS)
                text_color = QColor("#ffffff")
            elif i + 1 == self.current_step:
                fill = QColor(CLR_PRIMARY)
                text_color = QColor("#ffffff")
            else:
                fill = QColor(CLR_ACCENT)
                text_color = QColor(CLR_TEXT_MUTED)

            painter.setPen(Qt.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            # circle number
            painter.setFont(font_num)
            painter.setPen(text_color)
            painter.drawText(cx - r, cy - r, r * 2, r * 2, Qt.AlignCenter, str(i + 1))

            # label below
            painter.setFont(font_small)
            painter.setPen(QColor(CLR_TEXT_MUTED if i + 1 != self.current_step else CLR_TEXT))
            painter.drawText(cx - 36, cy + r + 2, 72, 30, Qt.AlignHCenter | Qt.AlignTop,
                             label.replace("\n", "\n"))

        painter.end()


# ------------------------------------------------------------------ #
# MetricsPanel                                                        #
# ------------------------------------------------------------------ #

class MetricsPanel(QFrame):
    """Shows sharpness + intensity as labelled bars."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {CLR_PANEL}; border: 1px solid {CLR_BORDER};"
            "border-radius: 8px; padding: 6px;"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self._sharp_lbl = make_label("Sharpness  :  —", 11)
        self._intens_lbl = make_label("Intensity   :  —", 11)

        self._sharp_bar = QProgressBar()
        self._intens_bar = QProgressBar()

        for bar, color in [
            (self._sharp_bar, "#3498db"),
            (self._intens_bar, "#e67e22"),
        ]:
            bar.setRange(0, 500)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setStyleSheet(
                f"QProgressBar {{ background: {CLR_ACCENT}; border-radius: 4px; }}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
            )

        layout.addWidget(self._sharp_lbl)
        layout.addWidget(self._sharp_bar)
        layout.addWidget(self._intens_lbl)
        layout.addWidget(self._intens_bar)

    def update_metrics(self, frame: np.ndarray, threshold: float = 50.0) -> None:
        if frame is None:
            return
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        inten = float(np.mean(gray))

        sharp_color = CLR_SUCCESS if sharp >= threshold else CLR_WARNING
        self._sharp_lbl.setText(f"Sharpness  :  {sharp:.1f}  (min {threshold:.0f})")
        self._sharp_lbl.setStyleSheet(f"color: {sharp_color}; background: transparent;")
        self._sharp_bar.setValue(min(int(sharp), 500))

        self._intens_lbl.setText(f"Intensity   :  {inten:.1f} / 255")
        self._intens_bar.setValue(min(int(inten * 500 / 255), 500))


# ------------------------------------------------------------------ #
# StatusBar                                                           #
# ------------------------------------------------------------------ #

class StatusBar(QLabel):
    """Full-width status message bar at the bottom of the window."""

    def __init__(self, parent=None):
        super().__init__("Ready", parent)
        self.setFixedHeight(30)
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.setStyleSheet(
            f"background: {CLR_ACCENT}; color: {CLR_TEXT};"
            "padding-left: 12px; font-size: 12px; border-radius: 0;"
        )

    def set_message(self, msg: str) -> None:
        self.setText(f"  {msg}")
