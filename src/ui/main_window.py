"""
MainWindow — Camera Test Bench v3 PyQt5 UI

Changes in this file:
  Change 1: Restart button shown above Abort after test completes
  Change 2: closeEvent (X button / Quit) offers Restart alongside Yes/No
  Change 3: When test is complete, Abort Test closes the app immediately
  Change 4: Serial dialog now has Exit Application button (handled in _on_request_serial)
  Change 5: GigE detection — no UI change needed, handled in camera_availability.py
  Change 6: Black image detection — handled in CaptureConfirmDialog, no change here

Keyboard routing rules
-----------------------
ALL buttons have Qt.NoFocus — keyboard never reaches them directly.
keyPressEvent is the single source of truth:
  SPACE  → _on_capture()  only when capture button is visible + enabled
  ENTER  → _on_proceed()  only when proceed button is visible + enabled
  Any other key → silently consumed, nothing happens.
Abort / Restart buttons are mouse-only.
"""

import sys
import numpy as np
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSplitter,
    QMessageBox, QSizePolicy, QApplication,
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
QPushButton#restart_btn {{
    background: #0f3460;
    color: #7ec8e3;
    border: 1px solid #1a5276;
    font-weight: bold;
}}
QPushButton#restart_btn:hover {{ background: #1a5276; }}
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
        self._test_complete = False          # Change 1/2/3: tracks completion state

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
        self.setWindowTitle("Camera Test Bench  v3.0")
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
        tb_layout.addWidget(make_label("v3.0", 11, color=CLR_TEXT_MUTED))
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

        # Left: camera feed
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

        # CAPTURE button
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

        # RESTART button — Change 1: shown above Abort after test completes
        self._btn_restart = QPushButton("↺  Restart Test")
        self._btn_restart.setObjectName("restart_btn")
        self._btn_restart.setFocusPolicy(Qt.NoFocus)
        self._btn_restart.setVisible(False)
        self._btn_restart.clicked.connect(self._on_restart)
        right_layout.addWidget(self._btn_restart)

        # ABORT button — mouse-only
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
        self._thread.request_trigger_count.connect(self._on_request_trigger_count)
        self._thread.hw_trigger_progress.connect(self._on_hw_trigger_progress)
        self._thread.hw_trigger_all_complete.connect(self._on_hw_trigger_all_complete)
        self._thread.exposure_preview_ready.connect(self._on_exposure_preview_ready)

        self._thread.start()

    # ------------------------------------------------------------------ #
    # Restart helper                                                       #
    # ------------------------------------------------------------------ #

    def _do_restart(self) -> None:
        """Stop the current thread and start a fresh workflow from step 1."""
        logger.info("Restarting test bench workflow")

        # Stop any running thread cleanly
        if self._thread.isRunning():
            self._thread.abort()
            self._thread.wait(3000)

        # Close any open progress dialog
        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.close()
            self._trigger_progress_dlg = None

        # Reset UI state
        self._test_complete = False
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        self._btn_restart.setVisible(False)
        self._progress.set_step(0)
        self._step_title_lbl.setText("")
        self._set_instruction("Starting…", "")
        self._feed._show_placeholder()
        self._status.set_message("Restarting …")

        # Build and start a fresh thread
        self._build_thread()
        logger.info("Fresh workflow thread started")

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
            1: "Enter the camera serial number shown on the camera label.\n\nA dialog will appear automatically.\n\nYou can also click Exit Application in the dialog to quit.",
            2: "The camera is live.\n\nVerify the feed looks correct, then press ENTER or click Proceed.",
            3: "Rotate the focus ring on the lens until the Sharpness score is stable and high.\n\nPress SPACE or click the button when focused.",
            4: "Press SPACE or click CAPTURE IMAGE to grab a single frame.\n\nThe backend will verify it automatically.",
            5: "Review the captured image.\n\nClick Accept to continue or Retake to capture again.\n\nAfter confirming, three exposure preview images will be shown automatically.",
            6: "Three sub-steps — LOW, MEDIUM, HIGH aperture.\n\nExposure is fixed constant for all three.\nPress SPACE at each position to capture.",
            7: "Camera is now in HARDWARE TRIGGER mode.\n\nRead the information dialog carefully, then click Continue.",
            8: "Press the physical push button wired to Line1 the required number of times.\n\nA progress dialog tracks each capture automatically.",
            9: "All hardware trigger images captured and saved.\n\nTest is complete  ✓\n\nClick Restart Test to run again, or close the window.",
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
    # Slot — step 5b exposure preview                                      #
    # ------------------------------------------------------------------ #

    @pyqtSlot(list)
    def _on_exposure_preview_ready(self, previews: list) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        dlg = ExposurePreviewDialog(previews, parent=self)
        dlg.exec_()
        self._thread.reply("proceed")
        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — serial (Change 4: handle Exit Application result)           #
    # ------------------------------------------------------------------ #

    @pyqtSlot(list)
    def _on_request_serial(self, available: list) -> None:
        dlg = SerialInputDialog(available, parent=self)
        result = dlg.exec_()

        if result == SerialInputDialog.Accepted and dlg.serial:
            # Normal confirm
            self._thread.reply(dlg.serial)

        elif result == SerialInputDialog.EXIT_CODE or dlg.exit_requested:
            # Change 4: operator clicked Exit Application — close cleanly
            self._thread.reply("abort")
            self._thread.wait(2000)
            QApplication.quit()
            return

        elif result == SerialInputDialog.Rejected:
            # Re-scan
            self._thread.reply("__rescan__")

        else:
            self._thread.reply("")

        self.setFocus()

    # ------------------------------------------------------------------ #
    # Slots — proceed gates                                                #
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_request_proceed(self, gate_id: str) -> None:
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
    # Slots — hardware trigger                                             #
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
        pass  # legacy single-image signal — multi-trigger uses hw_trigger_progress

    @pyqtSlot()
    def _on_request_trigger_count(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)

        dlg = TriggerCountDialog(parent=self)
        if dlg.exec_() == TriggerCountDialog.Accepted:
            count = dlg.trigger_count
            logger.info(f"Operator set trigger count: {count}")
            self._thread.reply(str(count))

            self._trigger_progress_dlg = HwTriggerProgressDialog(
                total=count, parent=self
            )
            self._trigger_progress_dlg.abort_requested.connect(self._on_trigger_abort)
            self._trigger_progress_dlg.show()
        else:
            self._thread.reply("abort")

        self.setFocus()

    @pyqtSlot(int, int, np.ndarray)
    def _on_hw_trigger_progress(self, captured: int, total: int,
                                 frame: np.ndarray) -> None:
        self._feed.update_frame(frame)
        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.update_progress(captured, frame)
        self._status.set_message(f"Hardware trigger: {captured} / {total} captured  ✓")

    @pyqtSlot(list)
    def _on_hw_trigger_all_complete(self, saved_paths: list) -> None:
        if self._trigger_progress_dlg is not None:
            self._trigger_progress_dlg.close()
            self._trigger_progress_dlg = None

        count = len(saved_paths)
        self._test_complete = True      # Change 1/2/3: mark test as done

        self._set_instruction(
            "Test Complete  ✓",
            f"All {count} hardware trigger image(s) captured and saved.\n\n"
            f"Images are in the results/ folder with timestamps.\n\n"
            "Click  ↺ Restart Test  to run again with the same or a new camera.\n"
            "Or close the window to exit."
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

        # Change 1: show Restart button above Abort
        self._btn_restart.setVisible(True)
        self.setFocus()

    def _on_trigger_abort(self) -> None:
        self._thread.abort()
        self._trigger_progress_dlg = None
        self._status.set_message("Hardware trigger capture aborted.")

    # ------------------------------------------------------------------ #
    # Button handlers                                                      #
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

    def _on_restart(self) -> None:
        """Change 1: Restart button clicked after test complete."""
        self._do_restart()

    def _on_abort(self) -> None:
        """Change 3: after test complete, Abort closes the app directly."""
        if self._test_complete:
            QApplication.quit()
            return

        # Mid-test abort — confirm first
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
        # Show restart so operator can try again without reopening the app
        self._btn_restart.setVisible(True)
        self.setFocus()

    @pyqtSlot()
    def _on_finished(self) -> None:
        self._btn_capture.setVisible(False)
        self._btn_proceed.setVisible(False)
        logger.info("Workflow thread finished")

    # ------------------------------------------------------------------ #
    # Keyboard handler                                                     #
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Space:
            if self._btn_capture.isVisible() and self._btn_capture.isEnabled():
                self._on_capture()
            return
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._btn_proceed.isVisible() and self._btn_proceed.isEnabled():
                self._on_proceed()
            return
        # All other keys — swallow silently

    # ------------------------------------------------------------------ #
    # Close (Change 2: X button offers Restart option)                    #
    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:
        """Change 2: When quitting mid-test offer Restart / Quit / Cancel.
           When test is complete, just quit cleanly.
        """
        if self._test_complete:
            # Test is done — close without asking
            event.accept()
            return

        if self._thread.isRunning():
            # Change 2: three-button dialog: Restart | Quit | Cancel
            msg = QMessageBox(self)
            msg.setWindowTitle("Quit Camera Test Bench")
            msg.setText(
                "A test is currently in progress.\n\n"
                "What would you like to do?"
            )
            msg.setIcon(QMessageBox.Question)
            btn_restart = msg.addButton("↺  Restart Test", QMessageBox.ResetRole)
            btn_quit    = msg.addButton("Quit",            QMessageBox.DestructiveRole)
            btn_cancel  = msg.addButton("Cancel",          QMessageBox.RejectRole)
            msg.setDefaultButton(btn_cancel)
            msg.exec_()

            clicked = msg.clickedButton()

            if clicked == btn_cancel:
                event.ignore()
                self.setFocus()
                return

            if clicked == btn_restart:
                event.ignore()       # don't close the window
                self._do_restart()
                return

            # Quit — fall through to accept
            if self._trigger_progress_dlg is not None:
                self._trigger_progress_dlg.close()
            self._thread.abort()
            self._thread.wait(3000)

        event.accept()
