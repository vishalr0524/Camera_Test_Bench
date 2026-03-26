"""
Camera Test Bench – Sequential Workflow Engine

Each step is a self-contained method.  Steps run in strict order;
none can be skipped.  The workflow uses OpenCV windows for display
and keyboard input so it works headlessly on a connected monitor.

Keyboard conventions (applied consistently across all steps):
    SPACE  – capture image (where applicable)
    ENTER  – accept / confirm / proceed
    R      – retake / retry current step
    Q      – quit the application at any point
"""

import sys
import time
import copy
from datetime import datetime
from typing import Optional, Dict, Any

import cv2
import numpy as np

from src.utils import get_logger, read_config
from src.hardware.camera.camera_availability import get_available_cameras
from src.hardware.camera.camera_factory import get_camera_class
from src.test_bench.image_verifier import (
    compute_sharpness,
    compute_mean_intensity,
    verify_capture,
    verify_aperture_sequence,
)
from src.test_bench.display_utils import (
    overlay_step_header,
    overlay_instruction,
    overlay_live_stats,
    overlay_capture_result,
    overlay_aperture_step,
    overlay_aperture_summary,
    overlay_hardware_trigger_wait,
    overlay_hardware_trigger_success,
    make_info_screen,
)
from src.test_bench.result_saver import ResultSaver

logger = get_logger(__name__)

# Key codes
KEY_SPACE = 32
KEY_ENTER = 13
KEY_R     = ord('r')
KEY_Q     = ord('q')
KEY_ESC   = 27

TOTAL_STEPS = 9
WINDOW_NAME = "Camera Test Bench"


class TestBenchWorkflow:
    """Runs the full camera test bench workflow sequentially."""

    def __init__(self, config_path: str = "configs/system_config.json") -> None:
        """Initialise the workflow.

        Args:
            config_path: Path to the system configuration JSON file.
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.tb_cfg: Dict[str, Any] = {}

        self.camera = None
        self.serial_num: str = ""
        self.saver: Optional[ResultSaver] = None

        self._load_config()
        logger.info("TestBenchWorkflow initialised")

    # ------------------------------------------------------------------ #
    # Config                                                               #
    # ------------------------------------------------------------------ #

    def _load_config(self) -> None:
        """Load system configuration from disk."""
        self.config = read_config(self.config_path)
        self.tb_cfg = self.config.get("test_bench", {})
        logger.info(f"Configuration loaded from: {self.config_path}")

    # ------------------------------------------------------------------ #
    # OpenCV window helpers                                                #
    # ------------------------------------------------------------------ #

    def _show(self, frame: np.ndarray) -> None:
        """Display frame in the main window."""
        cv2.imshow(WINDOW_NAME, frame)

    def _wait_key(self, delay_ms: int = 1) -> int:
        """Wait for a keypress and return the key code (lowercase)."""
        key = cv2.waitKey(delay_ms) & 0xFF
        if key in (KEY_Q, KEY_ESC):
            self._quit("User pressed Q/ESC – aborting test.")
        return key

    def _quit(self, reason: str = "") -> None:
        """Clean up and exit gracefully."""
        logger.info(f"Exiting: {reason}")
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
        cv2.destroyAllWindows()
        print(f"\n[Test Bench] {reason}")
        sys.exit(0)

    # ------------------------------------------------------------------ #
    # Step 1 – Serial number input & USB validation                       #
    # ------------------------------------------------------------------ #

    def step1_serial_validation(self) -> str:
        """Prompt the operator to enter the camera serial number and
        verify that the camera is physically connected via USB.

        Returns:
            Validated serial number string.
        """
        logger.info("=== STEP 1: Serial Number Validation ===")
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 900, 500)

        model = self.config.get("model", "basler")

        while True:
            # ---- fetch connected cameras ----
            print("\n" + "=" * 60)
            print("  STEP 1/9 – Camera Serial Number Validation")
            print("=" * 60)

            try:
                available = get_available_cameras(model)
            except Exception as e:
                available = []
                logger.error(f"Enumeration error: {e}")

            if not available:
                screen = make_info_screen(
                    title="STEP 1/9  –  Serial Number Validation",
                    lines=[
                        "No Basler cameras detected on this system.",
                        "",
                        "Please check:",
                        "  1. Camera USB cable is connected",
                        "  2. Camera is powered on",
                        "  3. Pylon drivers are installed",
                        "",
                        "Press R to rescan  |  Q to quit",
                    ],
                )
                self._show(screen)
                key = cv2.waitKey(0) & 0xFF
                if key in (KEY_Q, KEY_ESC):
                    self._quit("No cameras found – operator aborted.")
                continue  # R or any other key → rescan

            # ---- display available cameras ----
            available_str = "  Connected S/N(s): " + ",  ".join(available)
            print(available_str)
            print()

            screen = make_info_screen(
                title="STEP 1/9  –  Serial Number Validation",
                lines=[
                    "Detected camera(s) on this system:",
                    "",
                ] + [f"    •  {sn}" for sn in available] + [
                    "",
                    "Close this window and enter the serial number in the terminal.",
                    "",
                    "Press R to rescan  |  Q to quit",
                ],
            )
            self._show(screen)

            # Non-blocking check: if operator presses R → rescan; Q → quit
            key = cv2.waitKey(100) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted at Step 1.")

            # ---- terminal input ----
            serial_input = input("Enter camera serial number: ").strip()

            if not serial_input:
                print("[!] Serial number cannot be empty. Please try again.")
                continue

            if serial_input not in available:
                print(
                    f"[!] Serial number '{serial_input}' not found.\n"
                    f"    Connected cameras: {available}\n"
                    "    Please check the serial number and try again."
                )
                screen = make_info_screen(
                    title="STEP 1/9  –  Serial Validation FAILED",
                    lines=[
                        f"  Serial '{serial_input}' is NOT connected.",
                        "",
                        "  Connected cameras:",
                ] + [f"      •  {sn}" for sn in available] + [
                        "",
                        "  Press R to try again  |  Q to quit",
                    ],
                    title_color=(0, 50, 180),
                )
                self._show(screen)
                key = cv2.waitKey(0) & 0xFF
                if key in (KEY_Q, KEY_ESC):
                    self._quit("Operator aborted after serial mismatch.")
                continue

            # ---- serial validated ----
            self.serial_num = serial_input
            logger.info(f"Serial number validated: {self.serial_num}")

            screen = make_info_screen(
                title="STEP 1/9  –  Serial Validation PASSED  ✓",
                lines=[
                    f"  Camera S/N  :  {self.serial_num}",
                    f"  Status      :  Connected via USB",
                    "",
                    "  Initialising camera … please wait.",
                ],
                title_color=(0, 160, 50),
            )
            self._show(screen)
            cv2.waitKey(1200)

            print(f"[✓] Serial number '{self.serial_num}' validated successfully.\n")
            return self.serial_num

    # ------------------------------------------------------------------ #
    # Camera initialisation (between step 1 and 2)                        #
    # ------------------------------------------------------------------ #

    def _init_camera(self) -> None:
        """Build the camera config dict and instantiate the camera object."""
        cam_id = self.config["cameras"].get("cam_id", "camera_01")

        # Patch serial number into the config for this session
        runtime_config = copy.deepcopy(self.config)
        runtime_config["cameras"][cam_id]["serial_num"] = self.serial_num
        # Ensure software trigger for initial steps
        runtime_config["cameras"][cam_id]["trigger_mode"] = "software"

        model = runtime_config["cameras"][cam_id].get("model", "basler")
        CameraClass = get_camera_class(model)

        logger.info(f"Initialising {model} camera for S/N {self.serial_num}")
        self.camera = CameraClass(camera_config=runtime_config, cam_id=cam_id)
        logger.info("Camera object created and connected")

    # ------------------------------------------------------------------ #
    # Step 2 – Live feed                                                   #
    # ------------------------------------------------------------------ #

    def step2_live_feed(self) -> None:
        """Display a live camera feed so the operator can see the image.

        The step completes when the operator presses ENTER.
        """
        logger.info("=== STEP 2: Live Feed ===")
        print("\n" + "=" * 60)
        print("  STEP 2/9 – Live Feed")
        print("  Watch the live feed. Press ENTER when ready to focus.")
        print("=" * 60)

        sharpness_threshold = float(self.tb_cfg.get("sharpness_threshold", 50.0))

        while True:
            frame = self.camera.grab_image()
            if frame is None:
                continue

            # Compute stats
            sharpness = compute_sharpness(frame)
            mean_int  = compute_mean_intensity(frame)

            display = overlay_step_header(frame, step_num=2, total_steps=TOTAL_STEPS,
                                          title="Live Feed")
            display = overlay_live_stats(display, sharpness, mean_int, sharpness_threshold)
            display = overlay_instruction(
                display,
                lines=["Camera is live. Verify the feed looks correct."],
                key_hint="ENTER = proceed to focus step  |  Q = quit",
            )
            self._show(display)

            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted at Step 2.")
            if key == KEY_ENTER:
                logger.info("Step 2 complete – operator confirmed live feed")
                break

    # ------------------------------------------------------------------ #
    # Step 3 – Focus instruction                                           #
    # ------------------------------------------------------------------ #

    def step3_focus_object(self) -> None:
        """Instruct the operator to physically focus the camera on an object.

        A real-time sharpness score is shown on the feed.
        The step completes when SPACE is pressed to move to capture.
        """
        logger.info("=== STEP 3: Focus Object ===")
        print("\n" + "=" * 60)
        print("  STEP 3/9 – Focus the Camera")
        print("  Adjust the lens focus ring until the sharpness score is stable.")
        print("  Press SPACE when focused.")
        print("=" * 60)

        sharpness_threshold = float(self.tb_cfg.get("sharpness_threshold", 50.0))

        while True:
            frame = self.camera.grab_image()
            if frame is None:
                continue

            sharpness = compute_sharpness(frame)
            mean_int  = compute_mean_intensity(frame)

            display = overlay_step_header(frame, step_num=3, total_steps=TOTAL_STEPS,
                                          title="Focus Object")
            display = overlay_live_stats(display, sharpness, mean_int, sharpness_threshold)
            display = overlay_instruction(
                display,
                lines=[
                    "Adjust the camera FOCUS RING until the sharpness score is high.",
                    f"Target sharpness > {sharpness_threshold:.0f}  (current: {sharpness:.1f})",
                ],
                key_hint="SPACE = capture  |  Q = quit",
            )
            self._show(display)

            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted at Step 3.")
            if key == KEY_SPACE:
                logger.info(f"Step 3 complete – sharpness at capture: {sharpness:.1f}")
                break

    # ------------------------------------------------------------------ #
    # Step 4 – Capture & backend verification                              #
    # ------------------------------------------------------------------ #

    def step4_capture_and_verify(self) -> np.ndarray:
        """Capture a single frame and verify it passes quality checks.

        The operator may retake if unhappy.

        Returns:
            Accepted captured image (numpy BGR array).
        """
        logger.info("=== STEP 4: Capture & Verify ===")
        print("\n" + "=" * 60)
        print("  STEP 4/9 – Capture Image")
        print("  Press SPACE to capture. ENTER to accept. R to retake.")
        print("=" * 60)

        sharpness_threshold = float(self.tb_cfg.get("sharpness_threshold", 50.0))

        while True:
            # ---- show live feed until SPACE ----
            frame = self.camera.grab_image()
            if frame is None:
                cv2.waitKey(1)
                continue

            sharpness = compute_sharpness(frame)
            mean_int  = compute_mean_intensity(frame)

            display = overlay_step_header(frame, step_num=4, total_steps=TOTAL_STEPS,
                                          title="Capture Image")
            display = overlay_live_stats(display, sharpness, mean_int, sharpness_threshold)
            display = overlay_instruction(
                display,
                lines=["Press SPACE to capture the object."],
                key_hint="SPACE = capture  |  Q = quit",
            )
            self._show(display)

            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted at Step 4.")
            if key != KEY_SPACE:
                continue

            # ---- capture ----
            captured = self.camera.grab_image()
            if captured is None:
                logger.warning("Capture returned None – retrying")
                continue

            # ---- backend verification ----
            passed, details = verify_capture(captured, sharpness_threshold)
            logger.info(f"Capture verification: passed={passed}, details={details}")

            # ---- Step 5: show result to operator ----
            result_frame = overlay_capture_result(captured.copy(), passed, details)
            result_frame = overlay_step_header(result_frame, step_num=5,
                                               total_steps=TOTAL_STEPS,
                                               title="Confirm Captured Image")
            self._show(result_frame)

            print(f"\n  Capture result: {'PASS ✓' if passed else 'FAIL ✗'}")
            for k, v in details.items():
                print(f"    {k}: {v}")

            # ---- wait for operator decision ----
            while True:
                key2 = cv2.waitKey(0) & 0xFF
                if key2 in (KEY_Q, KEY_ESC):
                    self._quit("Operator aborted at Step 5.")
                if key2 == KEY_R:
                    logger.info("Operator chose to retake image")
                    print("  [Retaking…]")
                    break                 # inner loop → outer loop (new capture)
                if key2 == KEY_ENTER:
                    logger.info("Operator accepted captured image")
                    print("  [Image accepted]")
                    self.saver.save_image(captured, "step4_capture")
                    self.saver.record_step("step4_capture", {
                        "passed": passed,
                        **details,
                    })
                    return captured       # proceed to next step

    # ------------------------------------------------------------------ #
    # Step 6 – Aperture adjustment checks                                  #
    # ------------------------------------------------------------------ #

    def step6_aperture_check(self) -> None:
        """Guide the operator through low / correct / high aperture captures
        and validate that image intensity changes accordingly.
        """
        logger.info("=== STEP 6: Aperture Adjustment Check ===")
        print("\n" + "=" * 60)
        print("  STEP 6/9 – Aperture Adjustment Check")
        print("=" * 60)

        aperture_steps   = self.tb_cfg.get("aperture_steps",   ["low", "correct", "high"])
        aperture_exp_map = self.tb_cfg.get("aperture_exposures", {
            "low":     3000,
            "correct": 10000,
            "high":    30000,
        })
        sharpness_threshold = float(self.tb_cfg.get("sharpness_threshold", 50.0))

        intensities: Dict[str, float] = {}
        total = len(aperture_steps)

        for idx, step_name in enumerate(aperture_steps, start=1):
            exposure_us = int(aperture_exp_map.get(step_name, 10000))

            print(f"\n  Sub-step {idx}/{total}: {step_name.upper()} aperture (exposure={exposure_us} µs)")
            print(f"  Adjust the aperture ring to the {step_name.upper()} position.")
            print(f"  Press SPACE to capture when ready.")

            # Apply exposure for this sub-step
            self.camera.set_exposure(exposure_us)
            time.sleep(0.3)   # brief settling time

            while True:
                # ---- live feed ----
                frame = self.camera.grab_image()
                if frame is None:
                    cv2.waitKey(1)
                    continue

                sharpness = compute_sharpness(frame)
                mean_int  = compute_mean_intensity(frame)

                display = overlay_step_header(frame, step_num=6, total_steps=TOTAL_STEPS,
                                              title=f"Aperture – {step_name.upper()} ({idx}/{total})")
                display = overlay_live_stats(display, sharpness, mean_int, sharpness_threshold)
                display = overlay_instruction(
                    display,
                    lines=[
                        f"Set aperture to {step_name.upper()} position.",
                        f"Exposure locked to {exposure_us} µs for this step.",
                    ],
                    key_hint="SPACE = capture  |  Q = quit",
                )
                self._show(display)

                key = cv2.waitKey(1) & 0xFF
                if key in (KEY_Q, KEY_ESC):
                    self._quit("Operator aborted at Step 6.")
                if key != KEY_SPACE:
                    continue

                # ---- capture ----
                captured = self.camera.grab_image()
                if captured is None:
                    continue

                mean_captured = compute_mean_intensity(captured)
                intensities[step_name] = mean_captured
                logger.info(f"Aperture step '{step_name}': mean intensity = {mean_captured:.1f}")

                # ---- show result ----
                result_frame = overlay_aperture_step(
                    captured.copy(), step_name, idx, total,
                    exposure_us, mean_captured
                )
                result_frame = overlay_step_header(result_frame, step_num=6,
                                                   total_steps=TOTAL_STEPS,
                                                   title=f"Aperture – {step_name.upper()}")
                self._show(result_frame)

                # Save individual aperture image
                self.saver.save_image(captured, f"step6_aperture_{step_name}")

                print(f"  Captured – mean intensity = {mean_captured:.1f}")
                print("  Press ENTER to accept this step  |  R to retake  |  Q to quit")

                while True:
                    key2 = cv2.waitKey(0) & 0xFF
                    if key2 in (KEY_Q, KEY_ESC):
                        self._quit("Operator aborted at Step 6.")
                    if key2 == KEY_R:
                        logger.info(f"Operator retaking aperture step: {step_name}")
                        print("  [Retaking…]")
                        break   # redo this sub-step
                    if key2 == KEY_ENTER:
                        logger.info(f"Aperture sub-step accepted: {step_name}")
                        break   # move to next sub-step
                else:
                    continue
                break   # exit outer while True for this sub-step

        # ---- verify intensity trend ----
        passed, message = verify_aperture_sequence(intensities, aperture_steps)
        logger.info(f"Aperture sequence result: passed={passed}, msg={message}")

        # Display summary on a neutral frame (use last captured image)
        if 'captured' in dir() and captured is not None:
            summary_frame = overlay_aperture_summary(captured.copy(), passed, intensities, message)
        else:
            summary_frame = make_info_screen(
                title="STEP 6/9 – Aperture Summary",
                lines=[message],
                title_color=(0, 160, 50) if passed else (0, 50, 180),
            )
        self._show(summary_frame)

        print(f"\n  Aperture trend: {'PASS ✓' if passed else 'FAIL ✗'}")
        print(f"  {message}")

        self.saver.record_step("step6_aperture", {
            "passed": passed,
            "intensities": intensities,
            "message": message,
        })

        print("  Press ENTER to continue  |  Q to quit")
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted after Step 6.")
            if key == KEY_ENTER:
                break

    # ------------------------------------------------------------------ #
    # Step 7 – Switch to hardware trigger                                  #
    # ------------------------------------------------------------------ #

    def step7_enable_hardware_trigger(self) -> None:
        """Switch the camera to hardware trigger mode."""
        logger.info("=== STEP 7: Enable Hardware Trigger ===")
        print("\n" + "=" * 60)
        print("  STEP 7/9 – Switching to Hardware Trigger Mode")
        print("=" * 60)

        # Restore nominal exposure before hardware trigger
        default_exposure = self.config["cameras"].get(
            self.config["cameras"].get("cam_id", "camera_01"), {}
        ).get("exposure", 10000)
        try:
            self.camera.set_exposure(default_exposure)
        except Exception as e:
            logger.warning(f"Could not restore exposure: {e}")

        self.camera.set_trigger("hardware")
        logger.info("Camera switched to hardware trigger mode")

        self.saver.record_step("step7_hardware_trigger", {"enabled": True})

        screen = make_info_screen(
            title="STEP 7/9  –  Hardware Trigger Enabled",
            lines=[
                "Camera is now in HARDWARE TRIGGER mode.",
                "",
                "Trigger source : Line1 (configurable in system_config.json)",
                "Activation     : Rising Edge",
                "",
                "Press ENTER to proceed to the trigger test  |  Q to quit",
            ],
            title_color=(0, 130, 200),
        )
        self._show(screen)
        print("  Camera switched to HARDWARE TRIGGER mode.")
        print("  Press ENTER to continue.")

        while True:
            key = cv2.waitKey(0) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted at Step 7.")
            if key == KEY_ENTER:
                break

    # ------------------------------------------------------------------ #
    # Steps 8 & 9 – Hardware trigger capture                              #
    # ------------------------------------------------------------------ #

    def step8_9_hardware_trigger_capture(self) -> None:
        """Wait for the operator to press the push button (hardware trigger)
        and then display the captured image.
        """
        logger.info("=== STEPS 8-9: Hardware Trigger Capture ===")
        print("\n" + "=" * 60)
        print("  STEP 8/9 – Press the Push Button to trigger the camera")
        print("=" * 60)

        hw_timeout_ms = int(self.tb_cfg.get("hardware_trigger_timeout", 30000))

        # Clear any buffered frames
        try:
            self.camera.clear_buffer()
        except Exception:
            pass

        # ---- waiting loop ----
        start_time = time.time()
        captured = None
        print("  Waiting for hardware trigger… (press Q to abort)")

        while True:
            elapsed_ms = int((time.time() - start_time) * 1000)

            # Build a waiting display from a blank canvas
            wait_canvas = np.zeros((500, 900, 3), dtype=np.uint8)
            wait_canvas[:] = (25, 25, 25)
            display = overlay_hardware_trigger_wait(wait_canvas)

            # Add elapsed / timeout indicator
            remaining = max(0, hw_timeout_ms // 1000 - int(elapsed_ms / 1000))
            cv2.putText(
                display,
                f"Timeout in: {remaining}s",
                (700, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1,
            )
            self._show(display)

            # Try to grab (camera.grab_image returns None on timeout when hw trigger)
            captured = self.camera.grab_image()

            if captured is not None:
                logger.info("Hardware-triggered image received!")
                break

            # Check operator abort
            key = cv2.waitKey(1) & 0xFF
            if key in (KEY_Q, KEY_ESC):
                self._quit("Operator aborted while waiting for hardware trigger.")

            # Overall timeout
            if elapsed_ms >= hw_timeout_ms:
                logger.warning("Hardware trigger timeout – no image received")
                print("  [!] Timeout: no trigger received within the allowed time.")
                screen = make_info_screen(
                    title="STEP 8/9  –  Hardware Trigger TIMEOUT",
                    lines=[
                        "No trigger signal received within the timeout period.",
                        "",
                        "Please check:",
                        "  1. Push button wiring to trigger line (Line1)",
                        "  2. Camera trigger configuration in system_config.json",
                        "",
                        "Press R to retry  |  Q to quit",
                    ],
                    title_color=(0, 50, 180),
                )
                self._show(screen)

                while True:
                    key2 = cv2.waitKey(0) & 0xFF
                    if key2 in (KEY_Q, KEY_ESC):
                        self._quit("Operator aborted after hardware trigger timeout.")
                    if key2 == KEY_R:
                        start_time = time.time()   # reset timer
                        break
                if key2 == KEY_R:
                    continue   # restart wait loop

        # ---- Step 9: show success ----
        logger.info("=== STEP 9: Show Hardware Trigger Result ===")
        print("\n  STEP 9/9 – Hardware Trigger Image Captured!")

        success_frame = overlay_hardware_trigger_success(captured.copy())
        success_frame = overlay_step_header(
            success_frame, step_num=9, total_steps=TOTAL_STEPS,
            title="Hardware Trigger – Image Captured"
        )
        self._show(success_frame)

        self.saver.save_image(captured, "step8_hardware_triggered")
        self.saver.record_step("step8_9_hardware_trigger", {
            "passed": True,
            "image_shape": list(captured.shape),
        })

        print("  Hardware-triggered image captured and saved.")
        print("  Press ENTER or Q to finish.")

        while True:
            key = cv2.waitKey(0) & 0xFF
            if key in (KEY_Q, KEY_ESC, KEY_ENTER):
                break

    # ------------------------------------------------------------------ #
    # Entry point                                                          #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """Execute all test bench steps in strict sequential order."""
        print("\n" + "=" * 60)
        print("   CAMERA TEST BENCH")
        print("=" * 60)
        print(f"  Config : {self.config_path}")
        print(f"  Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # ---- Step 1: Serial validation ----
        serial = self.step1_serial_validation()

        # ---- Initialise result saver ----
        results_dir = self.tb_cfg.get("results_dir", "results")
        self.saver = ResultSaver(results_dir=results_dir, serial_num=serial)
        self.saver.record_step("step1_serial_validation", {
            "passed": True,
            "serial_num": serial,
        })

        # ---- Initialise camera ----
        print(f"\n  Connecting to camera S/N {serial}…")
        screen = make_info_screen(
            title="Initialising Camera …",
            lines=[f"Connecting to S/N: {serial}", "Please wait…"],
        )
        cv2.imshow(WINDOW_NAME, screen)
        cv2.waitKey(1)

        try:
            self._init_camera()
        except Exception as e:
            logger.error(f"Camera initialisation failed: {e}", exc_info=True)
            print(f"\n[ERROR] Could not connect to camera: {e}")
            err_screen = make_info_screen(
                title="Camera Initialisation FAILED",
                lines=[
                    f"Error: {e}",
                    "",
                    "Check cable, serial number, and Pylon drivers.",
                    "Press Q to exit.",
                ],
                title_color=(0, 50, 180),
            )
            cv2.imshow(WINDOW_NAME, err_screen)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return

        # ---- Steps 2-9 ----
        try:
            self.step2_live_feed()
            self.step3_focus_object()
            self.step4_capture_and_verify()   # also covers step 5
            self.step6_aperture_check()
            self.step7_enable_hardware_trigger()
            self.step8_9_hardware_trigger_capture()

        except SystemExit:
            pass   # _quit() already handled cleanup
        except Exception as e:
            logger.error(f"Unexpected error during workflow: {e}", exc_info=True)
            print(f"\n[ERROR] Unexpected error: {e}")
        finally:
            if self.camera:
                try:
                    self.camera.disconnect()
                except Exception:
                    pass
            if self.saver:
                report_path = self.saver.save_report()
                print(f"\n  Test report saved → {report_path}")
            cv2.destroyAllWindows()

        print("\n" + "=" * 60)
        print("  CAMERA TEST BENCH – COMPLETE")
        print("=" * 60)
