"""
MainWindow — Camera Test Bench v2 PyQt5 UI
==========================================
Wires WorkflowThread signals to the UI.
The entire workflow logic is untouched — this file is pure display / input.
"""

import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QIcon
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
        self._waiting_for: str = ""          # what the thread is waiting for
        self._last_frame: np.ndarray = None  # most recent live frame

        self._build_ui()
        self._build_thread()
        self.setStyleSheet(APP_STYLE)
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
        title_bar.setStyleSheet(f"background: {CLR_PANEL}; border-bottom: 1px solid {CLR_BORDER};")
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

        # CAPTURE button
        self._btn_capture = QPushButton("CAPTURE  [SPACE]")
        self._btn_capture.setObjectName("capture_btn")
        self._btn_capture.setEnabled(False)
        self._btn_capture.clicked.connect(self._on_capture)
        right_layout.addWidget(self._btn_capture)

        # PROCEED button
        self._btn_proceed = QPushButton("Proceed  [ENTER]")
        self._btn_proceed.setObjectName("proceed_btn")
        self._btn_proceed.setEnabled(False)
        self._btn_proceed.clicked.connect(self._on_proceed)
        right_layout.addWidget(self._btn_proceed)

        # ABORT button
        self._btn_abort = QPushButton("Abort Test")
        self._btn_abort.setObjectName("abort_btn")
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

        # Start immediately
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
        logger.info(f"UI: step {step} — {title}")

    def _instruction_for_step(self, step: int) -> str:
        return {
            1: "Enter the camera serial number shown on the camera label.\n\nA dialog will appear automatically.",
            2: "The camera is live.\n\nVerify the feed looks correct, then click Proceed.",
            3: "Rotate the focus ring on the lens until the Sharpness score is stable and high.\n\nPress CAPTURE when focused.",
            4: "Press CAPTURE to grab a single frame.\n\nThe backend will verify it automatically.",
            5: "Review the captured image and its metrics.\n\nAccept to continue or Retake to try again.",
            6: "Three sub-steps:\n  1. Set aperture to LOW\n  2. Set to CORRECT\n  3. Set to HIGH\n\nPress CAPTURE at each position.",
            7: "Camera is switching to HARDWARE TRIGGER mode.\n\nClick Proceed when ready.",
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
            # Operator clicked Re-scan — thread will rescan and call this again
            self._thread.reply("__rescan__")
        else:
            self._thread.reply("")

    # ------------------------------------------------------------------ #
    # Slots — proceed gates                                                #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_request_proceed(self, gate_id: str) -> None:
        """For step 7 show a modal dialog. For live/focus/capture gates
        just enable the relevant button and wait for operator click."""
        self._waiting_for = gate_id

        if gate_id == "hw_trigger_ready":
            dlg = ProceedDialog(gate_id, parent=self)
            dlg.exec_()
            self._thread.reply("proceed")
            return

        # For live_feed / focus / capture / aperture_* — enable buttons
        if gate_id == "live_feed":
            self._btn_proceed.setEnabled(True)
            self._btn_capture.setEnabled(False)
        elif gate_id == "focus":
            self._btn_capture.setEnabled(True)
            self._btn_proceed.setEnabled(False)
        elif gate_id == "capture":
            self._btn_capture.setEnabled(True)
            self._btn_proceed.setEnabled(False)
        elif gate_id.startswith("aperture_"):
            self._btn_capture.setEnabled(True)
            self._btn_proceed.setEnabled(False)

    # ------------------------------------------------------------------ #
    # Slots — capture confirm                                              #
    # ------------------------------------------------------------------ #

    @pyqtSlot(np.ndarray, dict)
    def _on_capture_ready(self, frame: np.ndarray, details: dict) -> None:
        self._btn_capture.setEnabled(False)
        self._feed.update_frame(frame)
        dlg = CaptureConfirmDialog(frame, details, parent=self)
        if dlg.exec_() == CaptureConfirmDialog.Accepted and dlg.accepted_image:
            self._thread.reply("accept")
        else:
            self._thread.reply("retake")

    # ------------------------------------------------------------------ #
    # Slots — aperture                                                     #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str, int, float, np.ndarray)
    def _on_aperture_ready(self, step_name: str, exposure_us: int,
                           mean_intensity: float, frame: np.ndarray) -> None:
        self._btn_capture.setEnabled(False)
        steps = ["low", "correct", "high"]
        idx   = steps.index(step_name) + 1 if step_name in steps else 1
        dlg   = ApertureConfirmDialog(step_name, idx, 3, exposure_us,
                                      mean_intensity, frame, parent=self)
        if dlg.exec_() == ApertureConfirmDialog.Accepted:
            self._thread.reply("accept")
        else:
            self._thread.reply("retake")

    @pyqtSlot(bool, dict, str)
    def _on_aperture_summary(self, passed: bool, intensities: dict, message: str) -> None:
        dlg = ApertureSummaryDialog(passed, intensities, message, parent=self)
        dlg.exec_()
        self._thread.reply("proceed")

    # ------------------------------------------------------------------ #
    # Slots — hardware trigger                                             #
    # ------------------------------------------------------------------ #

    @pyqtSlot()
    def _on_hw_trigger_waiting(self) -> None:
        self._btn_capture.setEnabled(False)
        self._btn_proceed.setEnabled(False)
        self._set_instruction(
            "Waiting for Hardware Trigger",
            "Press the physical push button wired to Line1.\n\n"
            "The camera will capture automatically when it receives the signal.\n\n"
            "Timeout: 30 seconds (auto-resets)."
        )
        self._status.set_message("Waiting for push button signal on Line1 …")

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

    # ------------------------------------------------------------------ #
    # Button handlers                                                      #
    # ------------------------------------------------------------------ #

    def _on_capture(self) -> None:
        """SPACE / CAPTURE button — replies 'capture' to the waiting thread."""
        self._btn_capture.setEnabled(False)
        self._thread.reply("capture")

    def _on_proceed(self) -> None:
        """ENTER / Proceed button."""
        self._btn_proceed.setEnabled(False)
        self._thread.reply("proceed")

    def _on_abort(self) -> None:
        reply = QMessageBox.question(
            self, "Abort Test",
            "Are you sure you want to abort the current test?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._thread.abort()
            self._status.set_message("Test aborted.")

    # ------------------------------------------------------------------ #
    # Error / finish                                                       #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        logger.error(f"Workflow error: {message}")
        QMessageBox.critical(self, "Workflow Error", f"An error occurred:\n\n{message}")
        self._status.set_message(f"Error: {message}")

    @pyqtSlot()
    def _on_finished(self) -> None:
        self._btn_capture.setEnabled(False)
        self._btn_proceed.setEnabled(False)
        logger.info("Workflow finished")

    # ------------------------------------------------------------------ #
    # Keyboard shortcuts                                                   #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Space and self._btn_capture.isEnabled():
            self._on_capture()
        elif key in (Qt.Key_Return, Qt.Key_Enter) and self._btn_proceed.isEnabled():
            self._on_proceed()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    # Close                                                                #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:
        if self._thread.isRunning():
            self._thread.abort()
            self._thread.wait(3000)
        event.accept()
