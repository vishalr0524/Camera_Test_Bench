# Camera Test Bench — Installation Guide

This guide is written for operators with no programming background.
Follow every step in order. Do not skip any step.

---

## What You Need Before Starting

- A PC running **Windows 10/11** or **Ubuntu 20.04 / 22.04 LTS**
- A **Basler USB 3.0 camera** (e.g. acA1920-40uc)
- A **USB 3.0 cable** (the blue port on the PC)
- Internet connection (for the first-time install only)

---

## WINDOWS — Step by Step

### 1. Install Python 3.10 or 3.11

1. Open your browser and go to: https://www.python.org/downloads/
2. Click **"Download Python 3.11.x"**
3. Run the installer
4. **IMPORTANT:** On the first screen, tick the box that says **"Add Python to PATH"** before clicking Install Now
5. Click **Install Now** and wait for it to finish
6. Open **Command Prompt** (press `Win + R`, type `cmd`, press Enter)
7. Type the following and press Enter to verify:
   ```
   python --version
   ```
   You should see something like `Python 3.11.9`

---

### 2. Install Basler Pylon Camera Software Suite

1. Go to: https://www.baslerweb.com/en/downloads/software-downloads/
2. Download **"Basler pylon Camera Software Suite"** for Windows
3. Run the installer and follow the prompts
4. When asked about developer packages, select **"Developer"** (includes Python bindings)
5. Restart your PC after installation

---

### 3. Copy the Camera Test Bench folder to your PC

1. Copy the `Camera_Test_Bench` folder to a location like `C:\Tools\Camera_Test_Bench`
2. Do not use a folder path that has spaces or special characters

---

### 4. Open Command Prompt in the project folder

1. Open File Explorer and navigate to `C:\Tools\Camera_Test_Bench`
2. Click the address bar at the top, type `cmd`, and press Enter
3. A Command Prompt window will open already in the right folder

---

### 5. Install Python packages

In the Command Prompt window, type this and press Enter:

```
pip install -r requirements.txt
```

Wait for it to finish. You will see lines of text scrolling — this is normal.
When you see the cursor return, it is done.

---

### 6. Connect the camera

1. Plug the Basler camera into a **USB 3.0 port** (blue port) on the PC
2. Wait 5 seconds for Windows to recognise the device
3. Open **Pylon Viewer** (from the Start Menu) to confirm the camera appears

---

### 7. Run the application

In the same Command Prompt window, type:

```
python test_bench_app_v2.py
```

The Camera Test Bench window will open. Follow the on-screen instructions.

---

### Windows Troubleshooting

| Problem | Fix |
|---------|-----|
| `python` is not recognised | Re-install Python and tick "Add to PATH" |
| `pip install` fails | Run Command Prompt as Administrator |
| Camera not found in Pylon Viewer | Try a different USB port; reinstall Pylon drivers |
| `ModuleNotFoundError: pypylon` | Run `pip install pypylon` in Command Prompt |
| Window opens but camera feed is black | Increase `exposure` value in `configs/system_config.json` |
| PyQt5 error on startup | Run `pip install PyQt5` in Command Prompt |

---
---

## LINUX (Ubuntu) — Step by Step

### 1. Install Python 3.10 or 3.11

Open a **Terminal** (press `Ctrl + Alt + T`) and run:

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y
python3.11 --version
```

You should see `Python 3.11.x`.

---

### 2. Install Basler Pylon on Linux

1. Go to: https://www.baslerweb.com/en/downloads/software-downloads/
2. Download the **pylon Camera Software Suite** `.deb` package for your architecture (usually amd64)
3. Install it:

```bash
cd ~/Downloads
sudo apt install ./pylon_*.deb
```

4. Add your user to the `pgrimageusers` group (required for USB access without sudo):

```bash
sudo usermod -aG pgrimageusers $USER
```

5. **Log out and log back in** for the group change to take effect

6. Verify by opening Pylon Viewer:

```bash
/opt/pylon/bin/pylonviewer &
```

The camera should appear.

---

### 3. Install system dependencies for PyQt5

```bash
sudo apt install python3-pyqt5 libxcb-xinerama0 libxcb-icccm4 \
  libxcb-image0 libxcb-keysyms1 libxcb-render-util0 -y
```

---

### 4. Copy the project and install Python packages

```bash
cp -r Camera_Test_Bench ~/Camera_Test_Bench
cd ~/Camera_Test_Bench
pip3 install -r requirements.txt
```

---

### 5. Run the application

```bash
cd ~/Camera_Test_Bench
python3 test_bench_app_v2.py
```

---

### Linux Troubleshooting

| Problem | Fix |
|---------|-----|
| `cannot open display` | Make sure you are logged into a desktop session, not SSH |
| `No cameras found` | Run `groups` and verify `pgrimageusers` is listed; if not, log out and in |
| PyQt5 platform plugin error | Run `sudo apt install libxcb-xinerama0` |
| `ImportError: libpylon.so` | Source Pylon environment: `source /opt/pylon/bin/pylon-setup-env.sh` |
| `pip3 install` permission error | Add `--user` flag: `pip3 install --user -r requirements.txt` |

---

## Verifying the Installation

After installation, run this quick check:

```
python test_bench_app_v2.py --help
```

If you see the help message, installation is complete.

---

## First Run Checklist

Before running with a real camera:

- [ ] Pylon Viewer shows the camera
- [ ] Camera serial number is visible on the camera body (printed label)
- [ ] USB 3.0 cable is plugged into a blue (USB 3.0) port
- [ ] `results/` folder is writable (it will be created automatically)
- [ ] For hardware trigger test: push button is wired to Line1 on the camera I/O connector

---

## Uninstalling

Simply delete the `Camera_Test_Bench` folder.
Python packages can be removed with `pip uninstall opencv-python pypylon PyQt5 numpy`.
