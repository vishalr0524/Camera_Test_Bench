"""
WorkflowThread — Camera Test Bench v3
======================================
Runs all 9 test steps in a QThread.  All communication to the UI is
via Qt signals.  The camera/verifier/saver code is NEVER modified.

v3 changes (step 8 only):
  • New signal  request_trigger_count()  — asks UI for number of triggers
  • New signal  hw_trigger_progress(int, int, np.ndarray)
                  → (captured_so_far, total, last_frame)
  • _step8_9 loops N times, saves each image, emits progress after each
  • Step 9 emits hw_trigger_all_complete(list) — list of saved file paths
"""

import copy
import time
from typing import Optional, Dict, Any, List

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from src.utils import get_logger, read_config
from src.hardware.camera.camera_availability import get_available_cameras
from src.hardware.camera.camera_factory import get_camera_class
from src.test_bench.image_verifier import (
    compute_sharpness,
    compute_mean_intensity,
    verify_capture,
    verify_aperture_sequence,
)
from src.test_bench.result_saver import ResultSaver

logger = get_logger(__name__)

TOTAL_STEPS = 9


class WorkflowThread(QThread):
    """Executes all 9 test bench steps sequentially in a background thread."""

    # ------------------------------------------------------------------ #
    # Signals                                                              #
    # ------------------------------------------------------------------ #
    step_changed             = pyqtSignal(int, str)
    status_update            = pyqtSignal(str)
    frame_ready              = pyqtSignal(np.ndarray)
    capture_ready            = pyqtSignal(np.ndarray, dict)
    aperture_ready           = pyqtSignal(str, int, float, np.ndarray)
    aperture_summary         = pyqtSignal(bool, dict, str)
    hw_trigger_waiting       = pyqtSignal()
    hw_trigger_captured      = pyqtSignal(np.ndarray)          # single image (legacy)
    hw_trigger_progress      = pyqtSignal(int, int, np.ndarray) # captured, total, frame  (v3)
    hw_trigger_all_complete  = pyqtSignal(list)                 # list of saved paths (v3)
    error_occurred           = pyqtSignal(str)
    finished_workflow        = pyqtSignal()
    serial_scan_done         = pyqtSignal(list)
    request_serial           = pyqtSignal(list)
    request_confirm          = pyqtSignal(str)
    request_aperture_confirm = pyqtSignal(str)
    request_proceed          = pyqtSignal(str)
    request_trigger_count    = pyqtSignal()                     # v3: ask UI for N

    def __init__(self, config_path: str = "configs/system_config.json") -> None:
        super().__init__()
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.tb_cfg: Dict[str, Any] = {}
        self.camera = None
        self.serial_num: str = ""
        self.saver: Optional[ResultSaver] = None

        self._mutex     = QMutex()
        self._condition = QWaitCondition()
        self._reply: str = ""

        self._abort = False

        self._load_config()

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #

    def _load_config(self) -> None:
        self.config = read_config(self.config_path)
        self.tb_cfg = self.config.get("test_bench", {})
        logger.info(f"Config loaded: {self.config_path}")

    # ------------------------------------------------------------------ #
    # Thread ↔ UI synchronisation                                         #
    # ------------------------------------------------------------------ #

    def _wait_for_ui(self, signal_to_emit: pyqtSignal, *args) -> str:
        """Emit signal, block until reply() is called from the UI thread."""
        self._mutex.lock()
        self._reply = ""
        signal_to_emit.emit(*args)
        self._condition.wait(self._mutex)
        reply = self._reply
        self._mutex.unlock()
        return reply

    def reply(self, value: str) -> None:
        """Called by the UI (main thread) to unblock the workflow thread."""
        self._mutex.lock()
        self._reply = value
        self._condition.wakeOne()
        self._mutex.unlock()

    def abort(self) -> None:
        self._abort = True
        self.reply("abort")

    def _check_abort(self) -> None:
        if self._abort:
            raise InterruptedError("Workflow aborted by operator")

    # ------------------------------------------------------------------ #
    # Camera init                                                          #
    # ------------------------------------------------------------------ #

    def _init_camera(self) -> None:
        cam_id = self.config["cameras"].get("cam_id", "camera_01")
        runtime_config = copy.deepcopy(self.config)
        runtime_config["cameras"][cam_id]["serial_num"] = self.serial_num
        runtime_config["cameras"][cam_id]["trigger_mode"] = "software"

        model = runtime_config["cameras"][cam_id].get("model", "basler")
        CameraClass = get_camera_class(model)
        self.camera = CameraClass(camera_config=runtime_config, cam_id=cam_id)
        logger.info(f"Camera ready: {self.serial_num}")

    # ------------------------------------------------------------------ #
    # QThread entry point                                                  #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        try:
            self._run_workflow()
        except InterruptedError as e:
            logger.info(f"Workflow interrupted: {e}")
            self.status_update.emit("Test aborted by operator.")
        except Exception as e:
            logger.error(f"Workflow error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            if self.camera:
                try:
                    self.camera.disconnect()
                except Exception:
                    pass
            if self.saver:
                try:
                    self.saver.save_report()
                except Exception:
                    pass
            self.finished_workflow.emit()

    def _run_workflow(self) -> None:
        # Step 1 — serial validation
        self.step_changed.emit(1, "Serial Number Validation")
        serial = self._step1_serial_validation()
        self._check_abort()

        results_dir = self.tb_cfg.get("results_dir", "results")
        self.saver = ResultSaver(results_dir=results_dir, serial_num=serial)
        self.saver.record_step("step1_serial_validation",
                               {"passed": True, "serial_num": serial})

        # Connect camera
        self.status_update.emit(f"Connecting to camera S/N {serial} …")
        self._init_camera()
        self.status_update.emit(f"Camera {serial} connected.")
        self._check_abort()

        # Steps 2 – 9
        self._step2_live_feed()
        self._check_abort()
        self._step3_focus_object()
        self._check_abort()
        self._step4_5_capture_and_verify()
        self._check_abort()
        self._step6_aperture_check()
        self._check_abort()
        self._step7_enable_hardware_trigger()
        self._check_abort()
        self._step8_9_hardware_trigger_capture()

    # ------------------------------------------------------------------ #
    # Step 1                                                               #
    # ------------------------------------------------------------------ #

    def _step1_serial_validation(self) -> str:
        logger.info("=== STEP 1: Serial Validation ===")
        model = self.config.get("model", "basler")

        while True:
            self._check_abort()
            try:
                available = get_available_cameras(model)
            except Exception as e:
                available = []
                logger.error(f"Enumeration error: {e}")

            self.serial_scan_done.emit(available)
            reply = self._wait_for_ui(self.request_serial, available)

            if reply == "abort":
                raise InterruptedError("Aborted at step 1")

            serial_input = reply.strip()
            if not serial_input:
                self.status_update.emit("Serial number cannot be empty.")
                continue
            if serial_input not in available:
                self.status_update.emit(
                    f"S/N '{serial_input}' not found. Connected: {available}"
                )
                continue

            self.serial_num = serial_input
            self.status_update.emit(f"Serial {serial_input} validated ✓")
            logger.info(f"Serial validated: {serial_input}")
            return serial_input

    # ------------------------------------------------------------------ #
    # Step 2                                                               #
    # ------------------------------------------------------------------ #

    def _step2_live_feed(self) -> None:
        logger.info("=== STEP 2: Live Feed ===")
        self.step_changed.emit(2, "Live Feed")
        self.status_update.emit("Camera live. Press ENTER when ready to focus.")
        self._reply = ""
        self.request_proceed.emit("live_feed")
        while self._reply != "proceed":
            self._check_abort()
            frame = self.camera.grab_image()
            if frame is not None:
                self.frame_ready.emit(frame)
            time.sleep(0.03)
        logger.info("Step 2 complete")

    # ------------------------------------------------------------------ #
    # Step 3                                                               #
    # ------------------------------------------------------------------ #

    def _step3_focus_object(self) -> None:
        logger.info("=== STEP 3: Focus Object ===")
        self.step_changed.emit(3, "Focus Camera")
        self.status_update.emit("Adjust focus ring. Press CAPTURE when sharp.")
        self._reply = ""
        self.request_proceed.emit("focus")
        while self._reply != "capture":
            self._check_abort()
            frame = self.camera.grab_image()
            if frame is not None:
                self.frame_ready.emit(frame)
            time.sleep(0.03)
        logger.info("Step 3 complete")

    # ------------------------------------------------------------------ #
    # Steps 4 + 5                                                          #
    # ------------------------------------------------------------------ #

    def _step4_5_capture_and_verify(self) -> None:
        logger.info("=== STEP 4/5: Capture & Verify ===")
        self.step_changed.emit(4, "Capture Image")
        sharpness_threshold = float(self.tb_cfg.get("sharpness_threshold", 50.0))

        while True:
            self._check_abort()
            self._reply = ""
            self.request_proceed.emit("capture")
            while self._reply != "capture":
                self._check_abort()
                frame = self.camera.grab_image()
                if frame is not None:
                    self.frame_ready.emit(frame)
                time.sleep(0.03)

            captured = self.camera.grab_image()
            if captured is None:
                self.status_update.emit("Capture failed — retrying")
                continue

            passed, details = verify_capture(captured, sharpness_threshold)
            logger.info(f"Capture verify: passed={passed}")

            self.step_changed.emit(5, "Confirm Captured Image")
            reply = self._wait_for_ui(self.capture_ready, captured, details)

            if reply == "retake":
                self.step_changed.emit(4, "Capture Image")
                self.status_update.emit("Retaking — press CAPTURE again.")
                continue

            self.saver.save_image(captured, "step4_capture")
            self.saver.record_step("step4_capture", {"passed": passed, **details})
            logger.info("Step 4/5 complete — image accepted")
            return

    # ------------------------------------------------------------------ #
    # Step 6                                                               #
    # ------------------------------------------------------------------ #

    def _step6_aperture_check(self) -> None:
        logger.info("=== STEP 6: Aperture Check ===")
        self.step_changed.emit(6, "Aperture Adjustment Check")

        aperture_steps   = self.tb_cfg.get("aperture_steps",   ["low", "correct", "high"])
        aperture_exp_map = self.tb_cfg.get("aperture_exposures", {
            "low": 3000, "correct": 10000, "high": 30000,
        })
        intensities: Dict[str, float] = {}

        for step_name in aperture_steps:
            exposure_us = int(aperture_exp_map.get(step_name, 10000))
            self.camera.set_exposure(exposure_us)
            time.sleep(0.3)
            self.status_update.emit(
                f"Set aperture to {step_name.upper()} position, then press CAPTURE."
            )

            while True:
                self._check_abort()
                self._reply = ""
                self.request_proceed.emit(f"aperture_{step_name}")
                while self._reply != "capture":
                    self._check_abort()
                    frame = self.camera.grab_image()
                    if frame is not None:
                        self.frame_ready.emit(frame)
                    time.sleep(0.03)

                captured = self.camera.grab_image()
                if captured is None:
                    continue

                mean_intensity = compute_mean_intensity(captured)
                intensities[step_name] = mean_intensity

                reply = self._wait_for_ui(
                    self.aperture_ready, step_name, exposure_us, mean_intensity, captured
                )
                if reply == "retake":
                    self.status_update.emit(f"Retaking {step_name} aperture step.")
                    continue
                self.saver.save_image(captured, f"step6_aperture_{step_name}")
                break

        passed, message = verify_aperture_sequence(intensities, aperture_steps)
        self.saver.record_step("step6_aperture", {
            "passed": passed, "intensities": intensities, "message": message,
        })
        self._wait_for_ui(self.aperture_summary, passed, intensities, message)
        logger.info("Step 6 complete")

    # ------------------------------------------------------------------ #
    # Step 7                                                               #
    # ------------------------------------------------------------------ #

    def _step7_enable_hardware_trigger(self) -> None:
        logger.info("=== STEP 7: Hardware Trigger ===")
        self.step_changed.emit(7, "Enable Hardware Trigger")

        default_exp = self.config["cameras"].get(
            self.config["cameras"].get("cam_id", "camera_01"), {}
        ).get("exposure", 10000)
        try:
            self.camera.set_exposure(default_exp)
        except Exception:
            pass

        self.camera.set_trigger("hardware")
        self.saver.record_step("step7_hardware_trigger", {"enabled": True})
        self.status_update.emit("Hardware trigger enabled. Click Continue when ready.")

        # Show info dialog in UI, then wait for operator to click Continue
        self._wait_for_ui(self.request_proceed, "hw_trigger_ready")
        logger.info("Step 7 complete")

    # ------------------------------------------------------------------ #
    # Steps 8 + 9  (v3 — multi-trigger with progress)                    #
    # ------------------------------------------------------------------ #

    def _step8_9_hardware_trigger_capture(self) -> None:
        logger.info("=== STEP 8/9: HW Trigger Capture (v3 multi-trigger) ===")
        self.step_changed.emit(8, "Set Number of Triggers")

        # Ask UI for how many triggers to capture — blocks until operator confirms
        reply = self._wait_for_ui(self.request_trigger_count)
        if reply == "abort":
            raise InterruptedError("Aborted at step 8 trigger count dialog")

        try:
            trigger_count = int(reply)
            if trigger_count < 1:
                trigger_count = 1
        except (ValueError, TypeError):
            trigger_count = 1

        logger.info(f"Operator requested {trigger_count} trigger capture(s)")
        self.status_update.emit(
            f"Waiting for {trigger_count} hardware trigger(s) — press the push button."
        )

        hw_timeout_ms = int(self.tb_cfg.get("hardware_trigger_timeout", 30000))

        try:
            self.camera.clear_buffer()
        except Exception:
            pass

        # Update step title to show capture in progress
        self.step_changed.emit(8, f"Press Push Button  (0 / {trigger_count})")
        self.hw_trigger_waiting.emit()

        saved_paths: List[str] = []
        captured_count = 0

        while captured_count < trigger_count:
            self._check_abort()

            start_time = time.time()

            # Wait for a single trigger image
            while True:
                self._check_abort()
                elapsed_ms = int((time.time() - start_time) * 1000)

                frame = self.camera.grab_image()
                if frame is not None:
                    break

                if elapsed_ms >= hw_timeout_ms:
                    self.status_update.emit(
                        f"Trigger timeout — check wiring. "
                        f"Still waiting for trigger {captured_count + 1} of {trigger_count}."
                    )
                    start_time = time.time()   # reset and keep waiting

                time.sleep(0.05)

            # One image received
            captured_count += 1
            image_name = f"step8_hw_trigger_{captured_count:03d}_of_{trigger_count:03d}"
            path = self.saver.save_image(frame, image_name)
            saved_paths.append(path)

            logger.info(
                f"HW trigger image {captured_count}/{trigger_count} saved: {image_name}"
            )

            # Update UI progress
            self.step_changed.emit(
                8, f"Press Push Button  ({captured_count} / {trigger_count})"
            )
            self.hw_trigger_progress.emit(captured_count, trigger_count, frame)
            self.status_update.emit(
                f"Captured {captured_count} / {trigger_count}  ✓"
                if captured_count < trigger_count
                else f"All {trigger_count} images captured  ✓"
            )

        # Record results
        self.saver.record_step("step8_9_hardware_trigger", {
            "passed":        True,
            "trigger_count": trigger_count,
            "images_saved":  len(saved_paths),
            "files":         saved_paths,
        })

        # Step 9 — complete
        self.step_changed.emit(9, "Test Complete")
        self.hw_trigger_all_complete.emit(saved_paths)
        self.status_update.emit(
            f"All {trigger_count} hardware trigger image(s) saved.  Test complete  ✓"
        )
        logger.info(f"Steps 8/9 complete — {trigger_count} image(s) saved")
