# Camera Test Bench — Operator User Manual

**Version 3.0**
This manual tells you everything you need to run the Camera Test Bench without
any help from a technical team. Read it once before your first test.

---

## Before You Start — Checklist

Complete this checklist every time before launching the application.

- [ ] Camera is connected to the PC via a **USB 3.0 (blue) port**
- [ ] Camera is powered on (LED on the camera body is lit)
- [ ] You can see the camera serial number printed on the label on the camera body
  *(example: 25041552 — it is usually 8 digits)*
- [ ] For the hardware trigger test (Step 8): push button is wired to the camera I/O connector
- [ ] Previous test results in the `results/` folder have been backed up if needed

---

## Starting the Application

Open a terminal / command prompt, navigate to the Camera Test Bench folder,
and type:

```
python test_bench_app_v2.py
```

The application window opens. You will see:

- **Title bar** — shows the current step number and name
- **Step progress bar** — 9 circles across the top, each one lights up as you complete steps
- **Camera feed** — large panel on the left showing the live image
- **Metrics panel** — below the feed, shows Sharpness and Intensity bars
- **Instruction panel** — top right, tells you exactly what to do at each step
- **Action button** — bottom right, the only button you need to click (changes per step)
- **Abort Test** — always visible at the bottom right, for emergencies only
- **Status bar** — thin bar at the very bottom, shows one-line status messages

---

## The 9 Steps — What Happens and What You Do

### Step 1 — Serial Number Validation

**What happens:**
The application scans the USB bus and lists every Basler camera it finds.
A dialog box appears showing the detected serial number(s).

**What you do:**
1. Look at the serial number printed on the camera body
2. The dialog will have already filled in the detected serial number
3. Confirm it matches the camera you are testing
4. Click **Confirm ✓**

**If no camera appears:**
- Check the USB cable is plugged into a blue (USB 3.0) port
- Click **Re-scan USB** in the dialog
- If still nothing, restart the camera and try again

**If you type a wrong serial:**
An error message appears. The dialog stays open — retype the correct number and click Confirm again.

---

### Step 2 — Live Feed

**What happens:**
The camera connects and the live feed appears in the main window.
The Sharpness and Intensity bars update in real time.

**What you do:**
- Watch the feed for a few seconds to confirm the camera is working
- Verify the image is not completely black or white
- When satisfied, click **"Feed looks good — Proceed [ENTER]"** or press `ENTER` on your keyboard

**If the image is very dark:**
This is an exposure issue — ask a technical person to increase the `exposure` value in the configuration file.

---

### Step 3 — Focus the Camera

**What happens:**
The live feed continues. The Sharpness score is shown in the metrics panel below the feed.
A higher Sharpness score means a sharper, better-focused image.

**What you do:**
1. Look at the **Sharpness** value in the metrics panel
2. Slowly rotate the **focus ring** on the camera lens
3. Watch the Sharpness number — keep rotating until it stops increasing and stays stable
4. When the image looks sharp and the number is stable, click **"Focus set — CAPTURE [SPACE]"** or press `SPACE`

**Tip:** Sharpness values above 50 are generally good. If the scene is very plain
(e.g. a white wall), the number will be low even when focused — this is normal.

---

### Step 4 — Capture Image

**What happens:**
The live feed continues. When you press SPACE or click the button, the camera
takes a single snapshot and the backend automatically checks it.

**What you do:**
1. Make sure the object you want to test is in frame and in focus
2. Press `SPACE` or click **"CAPTURE IMAGE [SPACE]"**
3. The application captures the image and checks the quality automatically

---

### Step 5 — Confirm Captured Image

**What happens:**
A dialog box appears showing the captured image alongside its measurements:
- **Resolution** — image size in pixels
- **Sharpness** — edge sharpness score
- **Intensity** — average brightness (0 = black, 255 = white)

A green "CAPTURE OK ✓" or yellow "Review Required" banner appears at the top.

**What you do:**
- If the image looks correct and the metrics are acceptable → click **Accept ✓**
- If the image is blurry, too dark, or incorrectly framed → click **Retake ↩**
  (you will go back to Step 4 and capture again)

---

### Step 6 — Aperture Adjustment Check

**What happens:**
This step checks that the camera lens aperture ring is working correctly.
You will capture three images:

| Sub-step | Aperture position | Exposure the app sets |
|----------|------------------|-----------------------|
| LOW      | Minimum opening  | 3,000 µs (short)     |
| CORRECT  | Working position | 10,000 µs (medium)   |
| HIGH     | Maximum opening  | 30,000 µs (long)     |

After all three, the application automatically verifies that the brightness
increased from LOW → CORRECT → HIGH.

**What you do for each sub-step:**

1. Read the instruction panel — it tells you which position to set (LOW, CORRECT, or HIGH)
2. Rotate the **aperture ring** on the lens to that position
3. Watch the live feed — the image should get darker (LOW) or brighter (HIGH)
4. Press `SPACE` or click the **Capture button** when the aperture is set
5. A dialog shows the captured image and its intensity reading
6. Click **Accept ✓** if correct, or **Retake ↩** to try again

**After all three captures:**
A summary dialog shows whether the intensity trend passed or failed:
- **PASS ✓** — intensity increased correctly from LOW to HIGH → aperture ring is working
- **FAIL ✗** — intensities are flat or reversed → check the aperture ring is not stuck

Click **Continue →** to move to the next step regardless of pass/fail.
*(The result is recorded in the test report.)*

---

### Step 7 — Enable Hardware Trigger

**What happens:**
The camera switches from software control to hardware trigger mode.
In this mode, the camera will only capture an image when it receives an
electrical signal on the Line1 pin from the push button.

A dialog appears explaining this.

**What you do:**
- Read the dialog information
- Make sure the push button cable is connected to the camera I/O connector (Line1 pin)
- Click **Continue →**

---

### Step 8 — Set Number of Triggers and Press Push Button

This step has two parts.

**Part A — Set the number of captures**

A dialog box appears asking:
*"How many trigger pulses do you want to capture?"*

- Use the up/down arrows (or type a number) to set how many images you want
- You can choose between 1 and 100
- Click **Start →**

**Part B — Press the push button**

A progress dialog opens showing:
- How many images have been captured so far
- A thumbnail of the most recently captured image
- A progress bar

**What you do:**
- Press the physical push button (connected to Line1) once for each capture
- Wait for the progress bar to update after each press before pressing again
- Repeat until the progress bar is full

**If the button is not working:**
- Check the push button cable is connected to Line1 on the camera I/O connector
- The status bar shows a timeout message if no signal arrives in 30 seconds
- The application keeps waiting — it will not skip — fix the wiring and press again

---

### Step 9 — Test Complete

**What happens:**
All images are saved automatically. A success message appears.

**What you do:**
- Click **OK** on the success dialog
- The test is complete — you may close the application

---

## Where Are My Results?

Every test run creates a folder automatically:

```
results/
└── 25041552_20260325_143022/
    ├── step4_capture.png
    ├── step6_aperture_low.png
    ├── step6_aperture_correct.png
    ├── step6_aperture_high.png
    ├── step8_hw_trigger_001_of_003.png
    ├── step8_hw_trigger_002_of_003.png
    ├── step8_hw_trigger_003_of_003.png
    └── test_report.json
```

The folder name contains the **serial number** and the **date and time** of the test.
The `test_report.json` file records pass/fail and measurements for every step —
this is the file to send to the technical team if any issues are found.

---

## Keyboard Shortcuts

| Key | Action | When it works |
|-----|--------|---------------|
| `SPACE` | Capture image | Steps 3, 4, 6 — when CAPTURE button is visible |
| `ENTER` | Proceed / Continue | Step 2, 7 — when Proceed button is visible |
| Mouse click | Any button | Always |

**Important:** The keyboard only works when the correct button is visible for that step.
Pressing SPACE during Step 2 (Live Feed) does nothing — you must click Proceed or press ENTER.

---

## Aborting a Test

**If something goes wrong** and you need to stop:

1. Click **Abort Test** (bottom right of the screen)
2. A confirmation dialog asks: *"Are you sure?"*
3. Click **Yes** to stop, or **No** to continue the test

The application saves whatever results were completed up to that point.

**If you accidentally close the window** (click the X button):
A confirmation dialog appears — click **No** to go back, or **Yes** to quit.

---

## Common Problems and Solutions

| What you see | What to do |
|---|---|
| No camera found in Step 1 | Check USB cable; restart camera; click Re-scan USB |
| Camera feed is completely black | The exposure is too low — contact your technical team |
| Sharpness score is always very low | Focus the lens carefully; if the scene has no texture the score will be low |
| Step 8 shows "Trigger timeout" | Check the push button wiring to Line1; try pressing the button again |
| Application shows an error dialog | Write down the error message and contact your technical team |
| Aperture trend FAIL | The aperture ring may be stuck or you rotated it in the wrong direction — retake the test |

---

## Do Not Change These Things

- Do not edit any files in the `src/` folder
- Do not delete the `configs/` folder or `system_config.json`
- Do not move the application to a folder path that contains spaces or special characters

If you need to change camera settings (exposure, trigger source, etc.),
contact your technical team — do not modify the configuration file yourself
unless you have been trained to do so.

---

## Quick Reference Card

```
STEP 1  → Confirm serial number in dialog         → click Confirm ✓
STEP 2  → Verify live feed looks correct           → press ENTER
STEP 3  → Adjust focus ring until sharp            → press SPACE
STEP 4  → Frame the object                         → press SPACE to capture
STEP 5  → Review image in dialog                   → click Accept ✓ or Retake ↩
STEP 6  → Set LOW / CORRECT / HIGH aperture        → press SPACE at each position
STEP 7  → Read hardware trigger info               → click Continue →
STEP 8  → Set number of triggers → press button N times
STEP 9  → Test complete — close the application
```
