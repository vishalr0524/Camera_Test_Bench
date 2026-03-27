"""
MainWindow — Camera Test Bench v2 PyQt5 UI
==========================================
Wires WorkflowThread signals to the UI.
The entire workflow logic is untouched — this file is pure display / input.

Keyboard routing rules
-----------------------
ALL buttons have Qt.NoFocus so they never receive keyboard events directly.
Every key press is handled exclusively in keyPressEvent():
  SPACE  → fires _on_capture()  only when capture button is visible + enabled
  ENTER  → fires _on_proceed()  only when proceed button is visible + enabled
  Any other key → ignored silently, never propagated to any widget
The Abort button is mouse-only — no keyboard shortcut at all.
"""

import sys
import numpy as np
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSplitter, QApplication,
    QMessageBox, QSizePolicy,
)

from src.ui.workflow_thread import WorkflowThread
from src.ui.widgets import (
    CameraFeedWidget, StepProgressWidget, MetricsPanel,
    StatusBar, make_label,
    CLR_BG, CLR_PANEL, CLR_ACCENT, CLR_PRIMARY, CLR_SUCCESS,
    CLR_WARNING, CLR_TEXT, CLR_TEXT_MUTED, CLR_BORDER,
)
from src.ui.dialogs import (
    SerialInputDialog, CaptureConfirmDialog,
    ApertureConfirmDialog, ApertureSummaryDialog, ProceedDialog,
)
from src.utils import get_logger

logger = get_logger(__name__)

APP_STYLE = f"""
QMainWindow, QWidget {{
    background: {CLR_BG};
    color: {CLR_TEXT};
    font-family: 'Segoe UI', 'Ubuntu', sans-serif;
}}
QSplitter::handle {{
    background: {CLR_BORDER};
    width: 1px;
}}
QPushButton {{
    background: {CLR_ACCENT};
    color: {CLR_TEXT};
    border: 1px solid {CLR_BORDER};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    min-width: 110px;
}}
QPushButton:hover   {{ background: {CLR_PRIMARY}; }}
QPushButton:disabled {{ background: #111122; color: {CLR_TEXT_MUTED}; }}
QPushButton#capture_btn {{
    background: {CLR_PRIMARY};
    color: #fff;
    font-size: 14px;
    font-weight: bold;
    min-height: 44px;
}}
QPushButton#capture_btn:hover {{ background: #c0392b; }}
QPushButton#proceed_btn {{
    background: {CLR_SUCCESS};
    color: #000;
    font-weight: bold;
}}
QPushButton#abort_btn {{
    background: #2c1010;
    color: #e74c3c;
    border: 1px solid #5c2020;
}}
QPushButton#abort_btn:hover {{ background: #5c2020; }}
"""


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, config_path: str = "configs/system_config.json") -> None:
        super().__init__()
        self.config_path = config_path
        self._sharpness_threshold = 50.0
        self._current_step = 0
        self._waiting_for: str = ""
        self._last_frame: np.ndarray = None

        self._build_ui()
        self._build_thread()
        self.setStyleSheet(APP_STYLE)

        # Give focus to the window itself on startup.
        # No button must ever hold keyboard focus — all key routing
        # is handled exclusively in keyPressEvent().
        self.setFocus()
        logger.info("MainWindow ready")

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle("Camera Test Bench  v2.0")
        self.setMinimumSize(1200, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ---- Title bar ----
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet(
            f"background: {CLR_PANEL}; border-bottom: 1px solid {CLR_BORDER};"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(18, 0, 18, 0)
        tb_layout.addWidget(make_label("Camera Test Bench", 16, bold=True))
        tb_layout.addWidget(make_label("v2.0", 11, color=CLR_TEXT_MUTED))
        tb_layout.addStretch()
        self._step_title_lbl = make_label("", 13, color=CLR_PRIMARY)
        tb_layout.addWidget(self._step_title_lbl)
        root.addWidget(title_bar)

        # ---- Step progress ----
        self._progress = StepProgressWidget()
        self._progress.setContentsMargins(20, 6, 20, 0)
        root.addWidget(self._progress)

        # ---- Main content splitter ----
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # Left: camera feed + metrics
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 8, 6, 8)
        left_layout.setSpacing(8)

        self._feed = CameraFeedWidget()
        left_layout.addWidget(self._feed)

        self._metrics = MetricsPanel()
        self._metrics.setFixedHeight(90)
        left_layout.addWidget(self._metrics)

        splitter.addWidget(left)

        # Right: instruction panel + controls
        right = QWidget()
        right.setFixedWidth(320)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 8, 14, 8)
        right_layout.setSpacing(12)

        self._instruction_frame = QFrame()
        self._instruction_frame.setStyleSheet(
            f"background: {CLR_PANEL}; border: 1px solid {CLR_BORDER}; border-radius: 8px;"
        )
        ifr_layout = QVBoxLayout(self._instruction_frame)
        ifr_layout.setContentsMargins(14, 12, 14, 12)
        self._instruction_title = make_label("Instructions", 12, bold=True)
        self._instruction_body  = make_label("Starting…", 11, color=CLR_TEXT_MUTED)
        self._instruction_body.setWordWrap(True)
        self._instruction_body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        ifr_layout.addWidget(self._instruction_title)
        ifr_layout.addWidget(self._instruction_body)
        ifr_layout.addStretch()
        right_layout.addWidget(self._instruction_frame, stretch=1)

        # ---- CAPTURE button ----
        # Qt.NoFocus: mouse-clickable only.
        # Keyboard activation via SPACE is handled exclusively in keyPressEvent.
        self._btn_capture = QPushButton("CAPTURE  [SPACE]")
        self._btn_capture.setObjectName("capture_btn")
        self._btn_capture.setFocusPolicy(Qt.NoFocus)   # ← prevents SPACE triggering this
        self._btn_capture.setEnabled(False)
        self._btn_capture.setVisible(False)
        self._btn_capture.clicked.connect(self._on_capture)
        right_layout.addWidget(self._btn_capture)

        # ---- PROCEED button ----
        self._btn_proceed = QPushButton("Proceed  [ENTER]")
        self._btn_proceed.setObjectName("proceed_btn")
        self._btn_proceed.setFocusPolicy(Qt.NoFocus)   # ← prevents ENTER triggering this
        self._btn_proceed.setEnabled(False)
        self._btn_proceed.setVisible(False)
        self._btn_proceed.clicked.connect(self._on_proceed)
        right_layout.addWidget(self._btn_proceed)

        # ---- ABORT button ----
        # Mouse-only. No keyboard shortcut. NoFocus prevents any key from reaching it.
        self._btn_abort = QPushButton("Abort Test")
        self._btn_abort.setObjectName("abort_btn")
        self._btn_abort.setFocusPolicy(Qt.NoFocus)     # ← THE ROOT CAUSE FIX
        self._btn_abort.clicked.connect(self._on_abort)
        right_layout.addWidget(self._btn_abort)

        splitter.addWidget(right)
        root.addWidget(splitter, stretch=1)

        # ---- Status bar ----
        self._status = StatusBar()
        root.addWidget(self._status)

    # ------------------------------------------------------------------ #
    # Workflow thread                                                       #
    # ------------------------------------------------------------------ #

    def _build_thread(self) -> None:
        self._thread = WorkflowThread(config_path=self.config_path)

        self._thread.step_changed.connect(self._on_step_changed)
        self._thread.status_update.connect(self._status.set_message)
        self._thread.frame_ready.connect(self._on_frame_ready)
        self._thread.capture_ready.connect(self._on_capture_ready)
        self._thread.aperture_ready.connect(self._on_aperture_ready)
        self._thread.aperture_summary.connect(self._on_aperture_summary)
        self._thread.hw_trigger_waiting.connect(self._on_hw_trigger_waiting)
        self._thread.hw_trigger_captured.connect(self._on_hw_trigger_captured)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.finished_workflow.connect(self._on_finished)
        self._thread.request_serial.connect(self._on_request_serial)
        self._thread.request_proceed.connect(self._on_request_proceed)

        self._thread.start()

    # ------------------------------------------------------------------ #
    # Slots — step events                                                  #
    # ------------------------------------------------------------------ #

    @pyqtSlot(int, str)
    def _on_step_changed(self, step: int, title: str) -> None:
        self._current_step = step
        self._progress.set_step(step)
        self._step_title_lbl.setText(f"Step {step}/9  —  {title}")
        self._set_instruction(title, self._instruction_for_step(step))
        # Restore focus to window on every step change
        self.setFocus()
        logger.info(f"UI: step {step} — {title}")

    def _instruction_for_step(self, step: int) -> str:
        return {
            1: "Enter the camera serial number shown on the camera label.\n\nA dialog will appear automatically.",
            2: "The camera is live.\n\nVerify the feed looks correct, then click Proceed or press ENTER.",
            3: "Rotate the focus ring on the lens until the Sharpness score is stable and high.\n\nPress SPACE or click the button when focused.",
            4: "Press SPACE or click CAPTURE IMAGE to grab a single frame.\n\nThe backend will verify it automatically.",
            5: "Review the captured image and its metrics.\n\nUse the dialog buttons to Accept or Retake.",
            6: "Three sub-steps:\n  1. Set aperture to LOW\n  2. Set to CORRECT\n  3. Set to HIGH\n\nPress SPACE at each position to capture.",
            7: "Camera is switching to HARDWARE TRIGGER mode.\n\nClick Proceed or press ENTER when ready.",
            8: "Press the physical push button wired to Line1 on the camera I/O connector.",
            9: "Hardware-triggered image captured successfully!\n\nTest is complete.",
        }.get(step, "")

    def _set_instruction(self, title: str, body: str) -> None:
        self._instruction_title.setText(title)
        self._instruction_body.setText(body)

    # ------------------------------------------------------------------ #
    # Slots — live feed                                                    #
    # ------------------------------------------------------------------ #

    @pyqtSlot(np.ndarray)
    def _on_frame_ready(self, frame: np.ndarray) -> None:
        self._last_frame = frame
        self._feed.update_frame(frame)
        self._metrics.update_metrics(frame, self._sharpness_threshold)

    # ------------------------------------------------------------------ #
    # Slots — serial                                                       #
    # ------------------------------------------------------------------ #

    @pyqtSlot(list)
    def _on_request_serial(self, available: list) -> None:
        dlg = SerialInputDialog(available, parent=self)
        if dlg.exec_() == SerialInputDialog.Accepted and dlg.serial:
            self._thread.reply(dlg.serial)
        elif dlg.result() == SerialInputDialog.Rejected:
            self._thread.reply("__rescan__")
        else:
            self._thread.reply("")
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — proceed gates                                                #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_request_proceed(self, gate_id: str) -> None:
        """Show/hide and relabel buttons based on which gate is active.
        Only one button is ever visible at a time."""
        self._waiting_for = gate_id

        # Step 7 — modal dialog only, no persistent button shown
        if gate_id == "hw_trigger_ready":
            dlg = ProceedDialog(gate_id, parent=self)
            dlg.exec_()
            self._thread.reply("proceed")
            self.setFocus()
            return

        # Hide both first — only the correct one will be shown below
        self._btn_capture.setVisible(False)
        self._btn_capture.setEnabled(False)
        self._btn_proceed.setVisible(False)
        self._btn_proceed.setEnabled(False)

        if gate_id == "live_feed":
            self._btn_proceed.setText("Feed looks good  —  Proceed  [ENTER]")
            self._btn_proceed.setVisible(True)
            self._btn_proceed.setEnabled(True)

        elif gate_id == "focus":
            self._btn_capture.setText("Focus set  —  CAPTURE  [SPACE]")
            self._btn_capture.setVisible(True)
            self._btn_capture.setEnabled(True)

        elif gate_id == "capture":
            self._btn_capture.setText("CAPTURE IMAGE  [SPACE]")
            self._btn_capture.setVisible(True)
            self._btn_capture.setEnabled(True)

        elif gate_id.startswith("aperture_"):
            step_name = gate_id.split("_", 1)[1].upper()
            self._btn_capture.setText(f"Capture  {step_name}  Aperture  [SPACE]")
            self._btn_capture.setVisible(True)
            self._btn_capture.setEnabled(True)

        # Always return focus to window — never to a button
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — capture confirm (step 5)                                    #
    # ------------------------------------------------------------------ #

    @pyqtSlot(np.ndarray, dict)
    def _on_capture_ready(self, frame: np.ndarray, details: dict) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        self._feed.update_frame(frame)
        dlg = CaptureConfirmDialog(frame, details, parent=self)
        if dlg.exec_() == CaptureConfirmDialog.Accepted and dlg.accepted_image:
            self._thread.reply("accept")
        else:
            self._thread.reply("retake")
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — aperture                                                     #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str, int, float, np.ndarray)
    def _on_aperture_ready(self, step_name: str, exposure_us: int,
                           mean_intensity: float, frame: np.ndarray) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        steps = ["low", "correct", "high"]
        idx   = steps.index(step_name) + 1 if step_name in steps else 1
        dlg   = ApertureConfirmDialog(step_name, idx, 3, exposure_us,
                                      mean_intensity, frame, parent=self)
        if dlg.exec_() == ApertureConfirmDialog.Accepted:
            self._thread.reply("accept")
        else:
            self._thread.reply("retake")
        self.setFocus()

    @pyqtSlot(bool, dict, str)
    def _on_aperture_summary(self, passed: bool, intensities: dict, message: str) -> None:
        dlg = ApertureSummaryDialog(passed, intensities, message, parent=self)
        dlg.exec_()
        self._thread.reply("proceed")
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — hardware trigger                                             #
    # ------------------------------------------------------------------ #

    @pyqtSlot()
    def _on_hw_trigger_waiting(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        self._set_instruction(
            "Waiting for Hardware Trigger",
            "Press the physical push button wired to Line1.\n\n"
            "The camera will capture automatically when it receives the signal.\n\n"
            "Timeout: 30 seconds (auto-resets)."
        )
        self._status.set_message("Waiting for push button signal on Line1 …")
        self.setFocus()

    @pyqtSlot(np.ndarray)
    def _on_hw_trigger_captured(self, frame: np.ndarray) -> None:
        self._feed.update_frame(frame)
        self._set_instruction(
            "Hardware Trigger — Success  ✓",
            "The push button signal was received and the image was captured.\n\n"
            "All steps complete. You may close the application."
        )
        self._status.set_message("Hardware trigger image captured  ✓  — Test complete.")
        QMessageBox.information(
            self, "Test Complete",
            "All 9 steps passed.\n\nResults saved to the results/ folder."
        )
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Button click handlers                                                #
    # ------------------------------------------------------------------ #

    def _on_capture(self) -> None:
        """Called by mouse click OR SPACE in keyPressEvent.
        Guard check ensures it only fires when the button is actually active."""
        if not self._btn_capture.isVisible() or not self._btn_capture.isEnabled():
            return
        self._btn_capture.setEnabled(False)
        self._btn_capture.setVisible(False)
        self._thread.reply("capture")
        self.setFocus()

    def _on_proceed(self) -> None:
        """Called by mouse click OR ENTER in keyPressEvent."""
        if not self._btn_proceed.isVisible() or not self._btn_proceed.isEnabled():
            return
        self._btn_proceed.setEnabled(False)
        self._btn_proceed.setVisible(False)
        self._thread.reply("proceed")
        self.setFocus()

    def _on_abort(self) -> None:
        """Mouse-only. No keyboard shortcut. Always confirms with Yes/No, default No."""
        reply = QMessageBox.question(
            self,
            "Abort Test",
            "Are you sure you want to abort the current test?\n\n"
            "All progress will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._thread.abort()
            self._btn_capture.setVisible(False)
            self._btn_proceed.setVisible(False)
            self._status.set_message("Test aborted by operator.")
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Error / finish                                                       #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        logger.error(f"Workflow error: {message}")
        QMessageBox.critical(self, "Workflow Error", f"An error occurred:\n\n{message}")
        self._status.set_message(f"Error: {message}")
        self.setFocus()

    @pyqtSlot()
    def _on_finished(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        logger.info("Workflow finished")

    # ------------------------------------------------------------------ #
    # Keyboard handler — ONLY place where keys are acted on               #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:
        """
        Single source of truth for all keyboard input.

        SPACE  → _on_capture(), but ONLY if capture button is visible+enabled.
        ENTER  → _on_proceed(), but ONLY if proceed button is visible+enabled.
        Anything else → silently consumed, nothing happens.

        super() is intentionally NOT called — this prevents Qt from
        routing any key to any button or child widget.
        """
        key = event.key()

        if key == Qt.Key_Space:
            if self._btn_capture.isVisible() and self._btn_capture.isEnabled():
                self._on_capture()
            # else: SPACE is pressed but capture is not active → do nothing
            return   # never propagate SPACE to any widget

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._btn_proceed.isVisible() and self._btn_proceed.isEnabled():
                self._on_proceed()
            # else: ENTER is pressed but proceed is not active → do nothing
            return   # never propagate ENTER to any widget

        # All other keys: swallow silently.
        # No super() call = no widget receives this key.

    # ------------------------------------------------------------------ #
    # Close — always confirm with Yes/No                                   #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:
        """Intercept the window X button — confirm before closing."""
        if self._thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Quit Camera Test Bench",
                "A test is currently in progress.\n\n"
                "Are you sure you want to quit?\n"
                "All progress will be lost.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                self.setFocus()
                return
            self._thread.abort()
            self._thread.wait(3000)
        event.accept()