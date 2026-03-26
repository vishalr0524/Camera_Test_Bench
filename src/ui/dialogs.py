"""
Modal dialogs for Camera Test Bench v2 UI.
"""

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QDialogButtonBox,
)

from src.ui.widgets import (
    CLR_BG, CLR_PANEL, CLR_ACCENT, CLR_PRIMARY,
    CLR_SUCCESS, CLR_WARNING, CLR_TEXT, CLR_TEXT_MUTED, CLR_BORDER,
    make_label,
)

DIALOG_STYLE = f"""
    QDialog {{
        background: {CLR_BG};
    }}
    QPushButton {{
        background: {CLR_ACCENT};
        color: {CLR_TEXT};
        border: 1px solid {CLR_BORDER};
        border-radius: 6px;
        padding: 8px 22px;
        font-size: 13px;
        min-width: 100px;
    }}
    QPushButton:hover {{
        background: {CLR_PRIMARY};
    }}
    QPushButton#accept_btn {{
        background: {CLR_SUCCESS};
        color: #000;
        font-weight: bold;
    }}
    QPushButton#accept_btn:hover {{
        background: #27ae60;
    }}
    QPushButton#retake_btn {{
        background: {CLR_WARNING};
        color: #000;
        font-weight: bold;
    }}
    QLineEdit {{
        background: {CLR_ACCENT};
        color: {CLR_TEXT};
        border: 1px solid {CLR_BORDER};
        border-radius: 6px;
        padding: 8px;
        font-size: 14px;
    }}
    QListWidget {{
        background: {CLR_ACCENT};
        color: {CLR_TEXT};
        border: 1px solid {CLR_BORDER};
        border-radius: 6px;
        font-size: 13px;
    }}
    QListWidget::item:selected {{
        background: {CLR_PRIMARY};
    }}
"""


def _frame_to_pixmap(frame: np.ndarray, max_w: int = 560, max_h: int = 380) -> QPixmap:
    rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    pix  = QPixmap.fromImage(qimg)
    return pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ------------------------------------------------------------------ #
# SerialInputDialog                                                   #
# ------------------------------------------------------------------ #

class SerialInputDialog(QDialog):
    """Step 1 — ask operator to enter / select a camera serial number."""

    def __init__(self, available: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step 1 — Serial Number Validation")
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)
        self.serial = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        layout.addWidget(make_label("Camera Serial Number Validation", 15, bold=True))
        layout.addWidget(make_label("Detected cameras on this system:", 11,
                                    color=CLR_TEXT_MUTED))

        self._list = QListWidget()
        self._list.setFixedHeight(100)
        if available:
            for sn in available:
                item = QListWidgetItem(f"  {sn}")
                self._list.addItem(item)
            self._list.setCurrentRow(0)
        else:
            self._list.addItem("  No cameras detected — check USB connection")
        layout.addWidget(self._list)

        layout.addWidget(make_label("Enter serial number:", 11))
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("e.g. 25041552")
        if available:
            self._edit.setText(available[0])
        layout.addWidget(self._edit)

        # Clicking a list item fills the text field
        self._list.currentTextChanged.connect(
            lambda t: self._edit.setText(t.strip())
        )

        btn_row = QHBoxLayout()
        self._btn_rescan  = QPushButton("Re-scan USB")
        self._btn_confirm = QPushButton("Confirm  ✓")
        self._btn_confirm.setObjectName("accept_btn")
        btn_row.addWidget(self._btn_rescan)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_confirm)
        layout.addLayout(btn_row)

        self._btn_confirm.clicked.connect(self._confirm)
        self._btn_rescan.clicked.connect(self.reject)   # caller rescans and re-opens
        self._edit.returnPressed.connect(self._confirm)

        if not available:
            self._btn_confirm.setEnabled(False)

    def _confirm(self):
        self.serial = self._edit.text().strip()
        self.accept()


# ------------------------------------------------------------------ #
# CaptureConfirmDialog                                                #
# ------------------------------------------------------------------ #

class CaptureConfirmDialog(QDialog):
    """Step 5 — show captured image with metrics, accept or retake."""

    def __init__(self, frame: np.ndarray, details: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step 5 — Confirm Captured Image")
        self.setMinimumWidth(640)
        self.setStyleSheet(DIALOG_STYLE)
        self.accepted_image = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        passed = "warning" not in details and "error" not in details
        verdict = "CAPTURE OK  ✓" if passed else "CAPTURE — Review Required"
        v_color = CLR_SUCCESS if passed else CLR_WARNING
        vlbl = make_label(verdict, 15, bold=True, color=v_color)
        layout.addWidget(vlbl)

        # Image preview
        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setPixmap(_frame_to_pixmap(frame))
        layout.addWidget(img_lbl)

        # Metrics grid
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet(
            f"background: {CLR_PANEL}; border-radius: 6px; padding: 8px;"
        )
        mf_layout = QVBoxLayout(metrics_frame)
        mf_layout.setSpacing(4)

        rows = [
            ("Resolution",  details.get("resolution",    "—")),
            ("Sharpness",   str(details.get("sharpness", "—"))),
            ("Intensity",   str(details.get("mean_intensity", "—"))),
        ]
        if "warning" in details:
            rows.append(("Warning", details["warning"]))
        if "error" in details:
            rows.append(("Error",   details["error"]))

        for k, v in rows:
            row = QHBoxLayout()
            row.addWidget(make_label(f"{k}:", 11, color=CLR_TEXT_MUTED))
            row.addWidget(make_label(v, 11))
            row.addStretch()
            mf_layout.addLayout(row)
        layout.addWidget(metrics_frame)

        # Buttons
        btn_row = QHBoxLayout()
        self._btn_retake = QPushButton("Retake  ↩")
        self._btn_retake.setObjectName("retake_btn")
        self._btn_accept = QPushButton("Accept  ✓")
        self._btn_accept.setObjectName("accept_btn")
        btn_row.addWidget(self._btn_retake)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_accept)
        layout.addLayout(btn_row)

        self._btn_retake.clicked.connect(self.reject)
        self._btn_accept.clicked.connect(self._accept)

    def _accept(self):
        self.accepted_image = True
        self.accept()


# ------------------------------------------------------------------ #
# ApertureConfirmDialog                                               #
# ------------------------------------------------------------------ #

class ApertureConfirmDialog(QDialog):
    """Step 6 sub-step — show aperture capture with intensity reading."""

    def __init__(self, step_name: str, idx: int, total: int,
                 exposure_us: int, mean_intensity: float,
                 frame: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Step 6 — Aperture: {step_name.upper()}")
        self.setMinimumWidth(600)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        layout.addWidget(
            make_label(f"Aperture Test  —  {step_name.upper()}  ({idx}/{total})",
                       15, bold=True)
        )

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setPixmap(_frame_to_pixmap(frame))
        layout.addWidget(img_lbl)

        info = QFrame()
        info.setStyleSheet(f"background: {CLR_PANEL}; border-radius: 6px; padding: 8px;")
        il = QHBoxLayout(info)
        il.addWidget(make_label(f"Exposure: {exposure_us} µs", 11))
        il.addStretch()
        il.addWidget(make_label(f"Mean Intensity: {mean_intensity:.1f} / 255", 11))
        layout.addWidget(info)

        btn_row = QHBoxLayout()
        self._btn_retake = QPushButton("Retake  ↩")
        self._btn_retake.setObjectName("retake_btn")
        self._btn_accept = QPushButton("Accept  ✓")
        self._btn_accept.setObjectName("accept_btn")
        btn_row.addWidget(self._btn_retake)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_accept)
        layout.addLayout(btn_row)

        self._btn_retake.clicked.connect(self.reject)
        self._btn_accept.clicked.connect(self.accept)


# ------------------------------------------------------------------ #
# ApertureSummaryDialog                                               #
# ------------------------------------------------------------------ #

class ApertureSummaryDialog(QDialog):
    """Step 6 end — show intensity trend pass/fail."""

    def __init__(self, passed: bool, intensities: dict, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step 6 — Aperture Summary")
        self.setMinimumWidth(480)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        verdict = "Aperture Trend  PASS  ✓" if passed else "Aperture Trend  FAIL  ✗"
        color   = CLR_SUCCESS if passed else CLR_PRIMARY
        layout.addWidget(make_label(verdict, 15, bold=True, color=color))

        for step, val in intensities.items():
            layout.addWidget(
                make_label(f"  {step.upper():<10}  intensity = {val:.1f}", 12)
            )

        layout.addWidget(make_label(message, 11, color=CLR_TEXT_MUTED))

        btn = QPushButton("Continue  →")
        btn.setObjectName("accept_btn")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)


# ------------------------------------------------------------------ #
# ProceedDialog                                                       #
# ------------------------------------------------------------------ #

class ProceedDialog(QDialog):
    """Generic 'press ENTER to continue' dialog."""

    TITLES = {
        "hw_trigger_ready": ("Step 7 — Hardware Trigger Mode", [
            "Camera is now in HARDWARE TRIGGER mode.",
            "",
            "Trigger source   :  Line1",
            "Trigger activation :  Rising Edge",
            "",
            "Click Continue when ready to test the push button.",
        ]),
    }

    def __init__(self, gate_id: str, parent=None):
        super().__init__(parent)
        title, lines = self.TITLES.get(gate_id, (f"Gate: {gate_id}", ["Press Continue."]))
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 20, 24, 16)

        layout.addWidget(make_label(title, 14, bold=True))
        for line in lines:
            layout.addWidget(make_label(line, 11, color=CLR_TEXT_MUTED if not line.strip() else CLR_TEXT))

        btn = QPushButton("Continue  →")
        btn.setObjectName("accept_btn")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)
