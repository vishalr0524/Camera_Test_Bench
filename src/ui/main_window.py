"""
MainWindow — Camera Test Bench v3 PyQt5 UI
==========================================
Wires WorkflowThread signals to the UI.
The entire workflow logic is untouched — this file is pure display / input.

v3 additions:
  _on_request_trigger_count()  — shows TriggerCountDialog, replies with N
  _on_hw_trigger_progress()    — updates HwTriggerProgressDialog live
  _on_hw_trigger_all_complete()— closes progress dialog, shows success screen

Keyboard routing rules
-----------------------
ALL buttons have Qt.NoFocus — keyboard never reaches them directly.
keyPressEvent is the single source of truth:
  SPACE  → _on_capture()  only when capture button is visible + enabled
  ENTER  → _on_proceed()  only when proceed button is visible + enabled
  Any other key → silently consumed, nothing happens
Abort button is mouse-only — no keyboard shortcut.
"""

import sys
import numpy as np
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSplitter,
    QMessageBox, QSizePolicy,
)

from src.ui.workflow_thread import WorkflowThread
from src.ui.widgets import (
    CameraFeedWidget, StepProgressWidget,
    StatusBar, make_label,
    CLR_BG, CLR_PANEL, CLR_ACCENT, CLR_PRIMARY, CLR_SUCCESS,
    CLR_WARNING, CLR_TEXT, CLR_TEXT_MUTED, CLR_BORDER,
)
from src.ui.dialogs import (
    SerialInputDialog, CaptureConfirmDialog,
    ApertureConfirmDialog, ApertureSummaryDialog, ProceedDialog,
    TriggerCountDialog, HwTriggerProgressDialog,
    ExposurePreviewDialog,
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
QPushButton:hover    {{ background: {CLR_PRIMARY}; }}
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
    """Top-level application window for Camera Test Bench v3."""

    def __init__(self, config_path: str = "configs/system_config.json") -> None:
        super().__init__()
        self.config_path = config_path
        self._current_step = 0
        self._waiting_for: str = ""
        self._last_frame: np.ndarray = None

        # v3: holds the live progress dialog during step 8
        self._trigger_progress_dlg: HwTriggerProgressDialog = None

        self._build_ui()
        self._build_thread()
        self.setStyleSheet(APP_STYLE)
        self.setFocus()
        logger.info("MainWindow v3 ready")

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        self.setWindowTitle("Camera Test Bench")
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
        tb_layout.addWidget(make_label("", 11, color=CLR_TEXT_MUTED))
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

        # CAPTURE button — keyboard handled in keyPressEvent
        self._btn_capture = QPushButton("CAPTURE  [SPACE]")
        self._btn_capture.setObjectName("capture_btn")
        self._btn_capture.setFocusPolicy(Qt.NoFocus)
        self._btn_capture.setEnabled(False)
        self._btn_capture.setVisible(False)
        self._btn_capture.clicked.connect(self._on_capture)
        right_layout.addWidget(self._btn_capture)

        # PROCEED button
        self._btn_proceed = QPushButton("Proceed  [ENTER]")
        self._btn_proceed.setObjectName("proceed_btn")
        self._btn_proceed.setFocusPolicy(Qt.NoFocus)
        self._btn_proceed.setEnabled(False)
        self._btn_proceed.setVisible(False)
        self._btn_proceed.clicked.connect(self._on_proceed)
        right_layout.addWidget(self._btn_proceed)

        # ABORT button — mouse-only, no keyboard shortcut
        self._btn_abort = QPushButton("Abort Test")
        self._btn_abort.setObjectName("abort_btn")
        self._btn_abort.setFocusPolicy(Qt.NoFocus)
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

        # Existing signals
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

        # v3 new signals
        self._thread.request_trigger_count.connect(self._on_request_trigger_count)
        self._thread.hw_trigger_progress.connect(self._on_hw_trigger_progress)
        self._thread.hw_trigger_all_complete.connect(self._on_hw_trigger_all_complete)
        self._thread.exposure_preview_ready.connect(self._on_exposure_preview_ready)

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
        self.setFocus()
        logger.info(f"UI: step {step} — {title}")

    def _instruction_for_step(self, step: int) -> str:
        instructions = {
            1: "Enter the camera serial number shown on the camera label.\n\nA dialog will appear automatically.",
            2: "The camera is live.\n\nVerify the feed looks correct, then press ENTER or click Proceed.",
            3: "Rotate the focus ring on the lens until the Sharpness score is stable and high.\n\nPress SPACE or click the button when focused.",
            4: "Press SPACE or click CAPTURE IMAGE to grab a single frame.\n\nThe backend will verify it automatically.",
            5: "Review the captured image.\n\nClick Accept to continue or Retake to capture again.\n\nAfter confirming, three exposure preview images will be shown automatically.",
            6: "Three sub-steps — LOW, MEDIUM, HIGH aperture.\n\nExposure is fixed constant for all three.\nPress SPACE at each position to capture.",
            7: "Camera is now in HARDWARE TRIGGER mode.\n\nRead the information dialog carefully, then click Continue.",
            8: "Press the physical push button wired to Line1 the required number of times.\n\nA progress dialog tracks each capture automatically.",
            9: "All hardware trigger images captured and saved.\n\nTest is complete  ✓",
        }
        return instructions.get(
            step,
            "Exposure Preview — viewing three images at different exposures.\nNo action required. Click OK to continue."
        )

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

    # ------------------------------------------------------------------ #
    # Slot — step 5b exposure preview (view-only, no operator input)      #
    # ------------------------------------------------------------------ #

    @pyqtSlot(list)
    def _on_exposure_preview_ready(self, previews: list) -> None:
        """Show ExposurePreviewDialog with the three exposure images.
        No input from operator — they view and click OK to continue.
        The images are already saved before this signal fires.
        """
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        dlg = ExposurePreviewDialog(previews, parent=self)
        dlg.exec_()
        # Unblock the workflow thread regardless of how dialog was closed
        self._thread.reply("proceed")
        self.setFocus()

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
        """Show/hide and relabel buttons based on which gate is active."""
        self._waiting_for = gate_id

        if gate_id == "hw_trigger_ready":
            dlg = ProceedDialog(gate_id, parent=self)
            dlg.exec_()
            self._thread.reply("proceed")
            self.setFocus()
            return

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
        steps = ["low", "medium", "high"]
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
    # Slots — hardware trigger (legacy single-image, kept for compatibility)
    # ------------------------------------------------------------------ #

    @pyqtSlot()
    def _on_hw_trigger_waiting(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        self._set_instruction(
            "Waiting for Hardware Triggers",
            "Press the physical push button wired to Line1.\n\n"
            "Each press captures and saves one image.\n\n"
            "A progress dialog tracks how many have been captured."
        )
        self._status.set_message("Waiting for hardware trigger pulses on Line1 …")
        self.setFocus()

    @pyqtSlot(np.ndarray)
    def _on_hw_trigger_captured(self, frame: np.ndarray) -> None:
        """Legacy single-image signal — not used in v3 multi-trigger flow."""
        pass

    # ------------------------------------------------------------------ #
    # Slots — v3 trigger count dialog (step 8)                            #
    # ------------------------------------------------------------------ #

    @pyqtSlot()
    def _on_request_trigger_count(self) -> None:
        """Show TriggerCountDialog, reply with the chosen count (or abort)."""
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)

        dlg = TriggerCountDialog(parent=self)
        if dlg.exec_() == TriggerCountDialog.Accepted:
            count = dlg.trigger_count
            logger.info(f"Operator set trigger count: {count}")
            self._thread.reply(str(count))

            # Open the progress dialog immediately (non-modal)
            self._trigger_progress_dlg = HwTriggerProgressDialog(
                total=count, parent=self
            )
            self._trigger_progress_dlg.abort_requested.connect(self._on_trigger_abort)
            self._trigger_progress_dlg.show()
        else:
            # Operator cancelled — abort the workflow
            self._thread.reply("abort")

        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — v3 per-image progress                                       #
    # ------------------------------------------------------------------ #

    @pyqtSlot(int, int, np.ndarray)
    def _on_hw_trigger_progress(self, captured: int, total: int,
                                 frame: np.ndarray) -> None:
        """Called after each trigger image is captured — update progress dialog."""
        self._feed.update_frame(frame)

        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.update_progress(captured, frame)

        self._status.set_message(f"Hardware trigger: {captured} / {total} captured  ✓")

    # ------------------------------------------------------------------ #
    # Slots — v3 all captures complete                                    #
    # ------------------------------------------------------------------ #

    @pyqtSlot(list)
    def _on_hw_trigger_all_complete(self, saved_paths: list) -> None:
        """All N trigger images captured — close progress dialog, show summary."""
        # Close the progress dialog
        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.close()
            self._trigger_progress_dlg = None

        count = len(saved_paths)
        self._set_instruction(
            "Test Complete  ✓",
            f"All {count} hardware trigger image(s) captured and saved.\n\n"
            f"Images are in the results/ folder with timestamps.\n\n"
            "You may close the application."
        )
        self._status.set_message(
            f"Test complete — {count} image(s) saved to results/  ✓"
        )

        QMessageBox.information(
            self,
            "Test Complete",
            f"All 9 steps passed.\n\n"
            f"{count} hardware trigger image(s) saved to the results/ folder.",
        )
        self.setFocus()

    def _on_trigger_abort(self) -> None:
        """Operator pressed Abort inside the progress dialog."""
        self._thread.abort()
        self._trigger_progress_dlg = None
        self._status.set_message("Hardware trigger capture aborted.")

    # ------------------------------------------------------------------ #
    # Button click handlers                                                #
    # ------------------------------------------------------------------ #

    def _on_capture(self) -> None:
        if not self._btn_capture.isVisible() or not self._btn_capture.isEnabled():
            return
        self._btn_capture.setEnabled(False)
        self._btn_capture.setVisible(False)
        self._thread.reply("capture")
        self.setFocus()

    def _on_proceed(self) -> None:
        if not self._btn_proceed.isVisible() or not self._btn_proceed.isEnabled():
            return
        self._btn_proceed.setEnabled(False)
        self._btn_proceed.setVisible(False)
        self._thread.reply("proceed")
        self.setFocus()

    def _on_abort(self) -> None:
        reply = QMessageBox.question(
            self,
            "Abort Test",
            "Are you sure you want to abort the current test?\n\nAll progress will be lost.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if self._trigger_progress_dlg is not None:
                self._trigger_progress_dlg.close()
                self._trigger_progress_dlg = None
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
        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.close()
            self._trigger_progress_dlg = None
        QMessageBox.critical(self, "Workflow Error", f"An error occurred:\n\n{message}")
        self._status.set_message(f"Error: {message}")
        self.setFocus()

    @pyqtSlot()
    def _on_finished(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        logger.info("Workflow finished")

    # ------------------------------------------------------------------ #
    # Keyboard handler                                                     #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:
        """
        Single source of truth for keyboard input.
        SPACE  → capture (only if button visible + enabled)
        ENTER  → proceed (only if button visible + enabled)
        All other keys → silently consumed, nothing happens.
        super() intentionally NOT called.
        """
        key = event.key()

        if key == Qt.Key_Space:
            if self._btn_capture.isVisible() and self._btn_capture.isEnabled():
                self._on_capture()
            return   # consume SPACE regardless

        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._btn_proceed.isVisible() and self._btn_proceed.isEnabled():
                self._on_proceed()
            return   # consume ENTER regardless

        # All other keys — swallow silently, no super() call

    # ------------------------------------------------------------------ #
    # Close                                                                #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:
        if self._thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Quit Camera Test Bench",
                "A test is currently in progress.\n\n"
                "Are you sure you want to quit?\nAll progress will be lost.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                event.ignore()
                self.setFocus()
                return
            if self._trigger_progress_dlg is not None:
                self._trigger_progress_dlg.close()
            self._thread.abort()
            self._thread.wait(3000)
        event.accept()
