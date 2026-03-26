# Camera Test Bench

An interactive, step-by-step camera validation tool for Basler USB cameras.
Designed to be handed over to operators with no programming background.

---

## Quick Start

```bash
# 1. Install dependencies (once)
pip install -r requirements.txt

# 2. Connect the Basler camera via USB

# 3. Run the test bench
python test_bench_app.py
```

That's it. The application will guide you through every step on screen.

---

## What the Test Bench Does

The workflow runs **nine sequential steps** — you cannot skip any step.

| Step | Action |
|------|--------|
| 1 | Enter the camera serial number — validated against connected USB cameras |
| 2 | Live feed is displayed so you can verify the camera is working |
| 3 | Adjust the focus ring while watching the on-screen sharpness score |
| 4 | Press **SPACE** to capture an image |
| 5 | Inspect the captured image and press **ENTER** to accept or **R** to retake |
| 6 | Capture three images at low / correct / high aperture — intensity trend is verified automatically |
| 7 | Camera switches to **hardware trigger** mode |
| 8 | Press the physical push button wired to the trigger line |
| 9 | Captured image is displayed with a success signal |

---

## Keyboard Controls

| Key | Action |
|-----|--------|
| `SPACE` | Capture image |
| `ENTER` | Accept / proceed |
| `R` | Retake / retry current step |
| `Q` or `ESC` | Quit the application |

---

## Hardware Setup

### Camera connection
- Connect the Basler camera to the PC via USB 3.0
- Verify Pylon drivers are installed: open **Pylon Viewer** and confirm the camera appears

### Hardware trigger (Step 7 onwards)
- Wire the push button `NO` contact between **Line1** and **GND** on the camera I/O connector
- The default trigger configuration is:
  - Source: `Line1`
  - Activation: `Rising Edge`
  - Selector: `FrameStart`
- These can be changed in `configs/system_config.json`

---

## Configuration

All settings live in `configs/system_config.json`.

### Key fields

```json
{
    "model": "basler",
    "cameras": {
        "cam_id": "camera_01",
        "camera_01": {
            "serial_num": "",          ← left blank; operator enters it at runtime
            "exposure": 10000,         ← microseconds
            "framerate": 10,
            "grab_timeout": 5000,      ← milliseconds
            "trigger_source": "Line1"
        }
    },
    "test_bench": {
        "sharpness_threshold": 50.0,  ← Laplacian variance; raise if lens is very sharp
        "hardware_trigger_timeout": 30000,
        "aperture_exposures": {
            "low":     3000,
            "correct": 10000,
            "high":    30000
        }
    }
}
```

> **Tip:** The serial number field in the config is intentionally left blank.
> The operator enters it at runtime during Step 1 and it is validated against the
> camera physically connected to the PC.

---

## Test Results

After each session a timestamped folder is created inside `results/`:

```
results/
└── 25041552_20240325_143022/
    ├── step4_capture.png
    ├── step6_aperture_low.png
    ├── step6_aperture_correct.png
    ├── step6_aperture_high.png
    ├── step8_hardware_triggered.png
    └── test_report.json
```

`test_report.json` contains pass/fail status and metrics for every step.

---

## Project Structure

```
Camera_Test_Bench/
├── test_bench_app.py          ← run this
├── requirements.txt
├── configs/
│   ├── system_config.json     ← main configuration
│   └── logging_config.json
├── src/
│   ├── exceptions/
│   │   ├── camera_exceptions.py
│   │   └── __init__.py
│   ├── hardware/
│   │   └── camera/
│   │       ├── camera.py           ← BaseCamera (abstract)
│   │       ├── basler.py           ← BaslerCamera implementation
│   │       ├── camera_factory.py   ← factory: model name → class
│   │       ├── camera_availability.py  ← USB enumeration
│   │       └── __init__.py
│   ├── test_bench/
│   │   ├── workflow.py         ← sequential test steps
│   │   ├── image_verifier.py   ← sharpness & intensity checks
│   │   ├── display_utils.py    ← OpenCV overlay helpers
│   │   ├── result_saver.py     ← image & JSON report saving
│   │   └── __init__.py
│   └── utils/
│       ├── config.py
│       ├── encoding.py
│       ├── logging_config.py
│       └── __init__.py
├── logs/                      ← auto-created on first run
└── results/                   ← auto-created on first run
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No Basler cameras found` | Check USB cable; install Pylon 7+ drivers; try a different USB port |
| `Serial number not found` | Confirm the S/N printed on the camera label matches exactly |
| `Image is completely black` | Increase exposure or check lens cap is removed |
| `Sharpness score is very low` | Rotate the focus ring slowly; ensure subject is at correct distance |
| `Hardware trigger timeout` | Check push button wiring to Line1; verify camera I/O pin-out in Pylon Viewer |
| Application window does not open | Ensure a display is connected; `DISPLAY` env var is set on Linux |

---

## Logs

Logs are written to `logs/CameraTestBench.log` and rotated daily.
To increase verbosity change `log_level` to `"DEBUG"` in `configs/logging_config.json`.
