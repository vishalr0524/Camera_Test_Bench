"""
Modal dialogs for Camera Test Bench v3 UI.

New in v3:
  TriggerCountDialog  — step 8: operator enters how many hardware triggers to capture
  HwTriggerProgressDialog — step 8: live progress bar while captures arrive
"""

import cv2
import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QProgressBar, QSpinBox,
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
    QSpinBox {{
        background: {CLR_ACCENT};
        color: {CLR_TEXT};
        border: 1px solid {CLR_BORDER};
        border-radius: 6px;
        padding: 8px;
        font-size: 18px;
        min-height: 40px;
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
    QProgressBar {{
        background: {CLR_ACCENT};
        border: 1px solid {CLR_BORDER};
        border-radius: 6px;
        text-align: center;
        color: {CLR_TEXT};
        font-size: 13px;
        min-height: 28px;
    }}
    QProgressBar::chunk {{
        background: {CLR_SUCCESS};
        border-radius: 5px;
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
        self._btn_rescan.clicked.connect(self.reject)
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
        layout.addWidget(make_label(verdict, 15, bold=True, color=v_color))

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignCenter)
        img_lbl.setPixmap(_frame_to_pixmap(frame))
        layout.addWidget(img_lbl)

        metrics_frame = QFrame()
        metrics_frame.setStyleSheet(
            f"background: {CLR_PANEL}; border-radius: 6px; padding: 8px;"
        )
        mf_layout = QVBoxLayout(metrics_frame)
        mf_layout.setSpacing(4)

        rows = [
            ("Resolution",  details.get("resolution",     "—")),
            ("Sharpness",   str(details.get("sharpness",  "—"))),
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
    """Generic 'click Continue' dialog — used for step 7 hardware trigger info."""

    TITLES = {
        "hw_trigger_ready": ("Step 7 — Hardware Trigger Mode", [
            "Camera is now in HARDWARE TRIGGER mode.",
            "",
            "Trigger source     :  Line1",
            "Trigger activation :  Rising Edge",
            "",
            "In the next step you will set how many trigger",
            "pulses to capture, then press the push button",
            "that number of times.",
            "",
            "Click Continue when ready.",
        ]),
    }

    def __init__(self, gate_id: str, parent=None):
        super().__init__(parent)
        title, lines = self.TITLES.get(gate_id, (f"Gate: {gate_id}", ["Press Continue."]))
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setStyleSheet(DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 20, 24, 16)

        layout.addWidget(make_label(title, 14, bold=True))
        for line in lines:
            color = CLR_TEXT_MUTED if not line.strip() else CLR_TEXT
            layout.addWidget(make_label(line, 11, color=color))

        btn = QPushButton("Continue  →")
        btn.setObjectName("accept_btn")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)


# ------------------------------------------------------------------ #
# TriggerCountDialog  (NEW in v3)                                     #
# ------------------------------------------------------------------ #

class TriggerCountDialog(QDialog):
    """Step 8 — operator sets how many hardware trigger captures to collect.

    Returns self.trigger_count (int) after accept().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step 8 — Set Number of Triggers")
        self.setMinimumWidth(460)
        self.setStyleSheet(DIALOG_STYLE)
        self.trigger_count: int = 1

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        layout.addWidget(make_label("Hardware Trigger Capture", 15, bold=True))
        layout.addWidget(make_label(
            "How many trigger pulses do you want to capture?", 11, color=CLR_TEXT_MUTED
        ))
        layout.addWidget(make_label(
            "Each time you press the push button, one image will be saved.", 11,
            color=CLR_TEXT_MUTED
        ))

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {CLR_BORDER};")
        layout.addWidget(line)

        # Spin box — large and clear for operators
        spin_row = QHBoxLayout()
        spin_row.addWidget(make_label("Number of captures:", 13))
        self._spin = QSpinBox()
        self._spin.setRange(1, 100)
        self._spin.setValue(1)
        self._spin.setFixedWidth(120)
        spin_row.addWidget(self._spin)
        spin_row.addStretch()
        layout.addLayout(spin_row)

        layout.addWidget(make_label(
            "After clicking Start, press the push button the required\n"
            "number of times. A progress bar will track each capture.",
            11, color=CLR_TEXT_MUTED
        ))

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_start  = QPushButton("Start  →")
        btn_start.setObjectName("accept_btn")
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_start)
        layout.addLayout(btn_row)

        btn_cancel.clicked.connect(self.reject)
        btn_start.clicked.connect(self._start)

    def _start(self):
        self.trigger_count = self._spin.value()
        self.accept()


# ------------------------------------------------------------------ #
# HwTriggerProgressDialog  (NEW in v3)                               #
# ------------------------------------------------------------------ #

class HwTriggerProgressDialog(QDialog):
    """Step 8 — non-blocking progress dialog shown while captures arrive.

    The workflow thread calls update_progress() after each capture.
    The dialog closes itself when all captures are complete.
    It is shown with show() (non-modal) so the main window can still
    receive signals and update the camera feed.
    """

    # Emitted when operator clicks Abort inside this dialog
    abort_requested = pyqtSignal()

    def __init__(self, total: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step 8 — Capturing Hardware Triggers")
        self.setMinimumWidth(500)
        self.setStyleSheet(DIALOG_STYLE)
        # Prevent operator from closing via X button during capture
        self.setWindowFlags(
            Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint
        )

        self._total    = total
        self._captured = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 20)

        layout.addWidget(
            make_label(f"Capturing  0 / {total}  hardware trigger images", 14, bold=True)
        )
        self._title_lbl = layout.itemAt(0).widget()

        layout.addWidget(make_label(
            "Press the push button each time to trigger a capture.\n"
            "Each press captures and saves one image automatically.",
            11, color=CLR_TEXT_MUTED
        ))

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, total)
        self._bar.setValue(0)
        self._bar.setFormat(f"0 / {total} captured")
        layout.addWidget(self._bar)

        # Live thumbnail of last captured image
        self._thumb = QLabel()
        self._thumb.setAlignment(Qt.AlignCenter)
        self._thumb.setFixedHeight(220)
        self._thumb.setStyleSheet(
            f"background: #0a0a14; border: 1px solid {CLR_BORDER}; border-radius: 6px;"
        )
        self._thumb.setText("Waiting for first trigger …")
        layout.addWidget(self._thumb)

        # Status label
        self._status_lbl = make_label("Waiting for push button …", 11, color=CLR_TEXT_MUTED)
        layout.addWidget(self._status_lbl)

        self._btn_abort = QPushButton("Abort")
        self._btn_abort.setObjectName("retake_btn")
        self._btn_abort.clicked.connect(self._on_abort)
        layout.addWidget(self._btn_abort, alignment=Qt.AlignRight)

    def update_progress(self, captured_count: int, last_frame: np.ndarray) -> None:
        """Called from MainWindow slot after each trigger image is received."""
        self._captured = captured_count
        self._bar.setValue(captured_count)
        self._bar.setFormat(f"{captured_count} / {self._total} captured")
        self._title_lbl.setText(
            f"Capturing  {captured_count} / {self._total}  hardware trigger images"
        )
        self._status_lbl.setText(f"Image {captured_count} saved  ✓")

        # Update thumbnail
        if last_frame is not None:
            pix = _frame_to_pixmap(last_frame, max_w=460, max_h=210)
            self._thumb.setPixmap(pix)

        if captured_count >= self._total:
            self._status_lbl.setText(f"All {self._total} images captured  ✓  Finishing …")
            self._btn_abort.setEnabled(False)

    def _on_abort(self):
        self.abort_requested.emit()
        self.close()
