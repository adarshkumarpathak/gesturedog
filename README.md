# 🐾 GestureDog

> **Real-time hand gesture controlled robot dog using computer vision and cognitive robotics**

GestureDog is a cognitive robotics project that lets you control a **Waveshare WAVEGO 12-DOF bionic robot dog** using only hand gestures. The system uses MediaPipe to detect 21 hand landmarks in real time, classifies them into 10 distinct gestures, and sends commands wirelessly to the robot — all following the **Sense → Plan → Act** cognitive architecture.

---

## 📸 Demo

> Show your hand → Robot reacts in real time

| Gesture | Action |
|---------|--------|
| ✋ Open Palm | STOP |
| ✊ Fist | STAND |
| ☝️ Index Finger | Walk Forward |
| ✌️ Peace Sign | Walk Backward |
| 🤙 Call Me | Spin Left |
| 🖕 Middle Finger | Spin Right |
| 🤟 3 Fingers | Jump |
| 👎 Thumbs | Lay Low |
| 🤘 Rock Sign | Handshake |
| 🖖 4 Fingers | Balance Mode |

---

## 🧠 How It Works

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        LAPTOP                                │
│                                                              │
│  Pi Camera Stream → MediaPipe → Gesture Classifier           │
│                                      ↓                       │
│                              Debounce Filter                 │
│                                      ↓                       │
│                            TCP Socket Command                │
└──────────────────────────────────────────────────────────────┘
                               ↕ WiFi
┌──────────────────────────────────────────────────────────────┐
│                      RASPBERRY PI 4                          │
│                                                              │
│  Camera Stream Server (port 8080) ← Pi Camera               │
│  Command Receiver (port 9999) → JSON serial command          │
└──────────────────────────────────────────────────────────────┘
                           ↕ UART /dev/serial0
┌──────────────────────────────────────────────────────────────┐
│                         ESP32                                │
│                                                              │
│  JSON Parser → IK Engine → 12x Servo PWM                    │
└──────────────────────────────────────────────────────────────┘
```

### Cognitive Robotics — Sense → Plan → Act

| Layer | Component | What it does |
|-------|-----------|-------------|
| **Sense** | Pi Camera + MediaPipe | Converts raw pixels into 21 structured 3D hand landmarks |
| **Plan** | Gesture Classifier + Debounce | Maps landmark geometry to symbolic human intent |
| **Act** | pyserial + ESP32 | Executes physical robot behavior from intent |

### Gesture Classification

Each gesture is identified using a **binary finger state array** `[Thumb, Index, Middle, Ring, Pinky]`:

- **Fingers 2-5:** Compare tip Y coordinate vs PIP joint Y — if tip is higher = finger is up = `1`
- **Thumb:** Compare tip X vs IP joint X — extended = `1`
- Result: pattern like `[0,1,0,0,0]` = only index up = **WALK FORWARD**

### Debouncing

The system requires the **same gesture for 7 consecutive frames** before firing a command. This:
- Eliminates false triggers from hand tremor
- Models **selective attention** — a key cognitive phenomenon
- Combined with a **1.5 second cooldown** between commands

### Auto-Stop Safety

If no hand is detected for **1 second**, the robot automatically stops. This prevents runaway behavior and models reactive safety in cognitive systems.

---

## 🛠️ Hardware Requirements

| Component | Details |
|-----------|---------|
| Robot Dog | Waveshare WAVEGO 12-DOF Bionic Dog |
| Host Controller | Raspberry Pi 4 (onboard) |
| Sub Controller | ESP32 (onboard) |
| Camera | Pi Camera Module (onboard) |
| Laptop | Windows/Mac/Linux with Python 3.9+ |
| Network | Both laptop and Pi on same WiFi |

---

## 💻 Software Requirements

### Laptop
```
Python 3.9+
mediapipe
opencv-python
numpy
pyserial
loguru
requests
```

### Raspberry Pi
```
Python 3.9
flask
pyserial
loguru
opencv-python
```

---

## 🚀 Installation & Setup

### Step 1 — Clone Repository

```bash
git clone https://github.com/adarshkumarpathak/gesturedog.git
cd gesturedog
```

### Step 2 — Install Laptop Dependencies

```bash
pip install mediapipe opencv-python numpy pyserial loguru requests
```

### Step 3 — Download MediaPipe Hand Landmark Model

```powershell
# Windows PowerShell
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -OutFile "hand_landmarker.task"
```

```bash
# Linux/Mac
curl -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task
```

### Step 4 — Install Pi Dependencies

SSH into the Pi and install:

```bash
pip install flask pyserial loguru --break-system-packages
```

### Step 5 — Copy Pi Scripts to Robot

```bash
scp receiver.py stream_server.py pi@raspberrypi.local:/home/pi/gesturedog/
```

### Step 6 — Configure IP Address

Open `gesturedog.py` and update the Pi's IP:

```python
PI_IP = '10.141.192.172'   # Change to your Pi's IP
```

Find your Pi's IP by running on the Pi:
```bash
hostname -I
```

---

## ▶️ Running GestureDog

### 1. SSH Into Pi

```bash
ssh pi@raspberrypi.local
# password: raspberry
```

### 2. Kill Any Existing Processes

```bash
sudo pkill -9 -f python3
sudo fuser -k /dev/video0
tmux kill-server 2>/dev/null
sleep 2
```

### 3. Start Pi Services

```bash
tmux new-session -d -s stream 'python3 /home/pi/gesturedog/stream_server.py'
sleep 3
tmux new-session -d -s recv 'python3 /home/pi/gesturedog/receiver.py'
tmux ls   # should show: stream + recv
```

### 4. Start GestureDog on Laptop

```bash
python gesturedog.py
```

A window opens showing the live Pi camera feed with hand landmark overlay.

---

## ✋ Gesture Reference

> Hold each gesture steady until the **confidence bar turns green** (~1 second)

| # | Gesture | Finger State | Command | ESP32 JSON |
|---|---------|-------------|---------|------------|
| 1 | ✋ Open Palm | `[1,1,1,1,1]` | STOP | `{"var":"move","val":3+6}` |
| 2 | ✊ Fist | `[0,0,0,0,0]` | STAND | `{"var":"move","val":3+6}` |
| 3 | ☝️ Index Only | `[0,1,0,0,0]` | WALK FORWARD | `{"var":"move","val":1}` |
| 4 | ✌️ Peace Sign | `[0,1,1,0,0]` | WALK BACKWARD | `{"var":"move","val":5}` |
| 5 | 🤙 Call Me | `[1,0,0,0,1]` | SPIN LEFT | `{"var":"move","val":2}` |
| 6 | 🖕 Middle Only | `[0,0,1,0,0]` | SPIN RIGHT | `{"var":"move","val":4}` |
| 7 | 🤟 3 Fingers | `[0,1,1,1,0]` | JUMP | `{"var":"funcMode","val":4}` |
| 8 | 👎 Thumb Only | `[1,0,0,0,0]` | LAY LOW | `{"var":"funcMode","val":2}` |
| 9 | 🤘 Rock Sign | `[0,1,0,0,1]` | HANDSHAKE | `{"var":"funcMode","val":3}` |
| 10 | 🖖 4 Fingers | `[0,1,1,1,1]` | BALANCE | `{"var":"funcMode","val":1}` |

---

## 📊 HUD Display

```
┌────────────────────────────────┐
│ Gesture: WALK_FORWARD          │  ← Detected gesture (green)
│ Command: WALK_FORWARD          │  ← Last command sent (cyan)
│ Total:   12 cmds               │  ← Session command count
│ No hand: 0.5s                  │  ← Auto-stop countdown (red)
│                                │
│ [████████░░] Hold to confirm   │  ← Confidence bar (orange→green)
└────────────────────────────────┘
```

---

## 📁 Project Structure

```
gesturedog/
├── gesturedog.py          # Main laptop script — MediaPipe + gesture control
├── receiver.py            # Pi script — receives commands, sends to ESP32
├── stream_server.py       # Pi script — serves MJPEG camera stream
├── hand_landmarker.task   # MediaPipe hand landmark model
├── logs/                  # Auto-generated session logs
└── README.md
```

---

## 📝 Session Logging

Every session is automatically logged to `logs/session_YYYYMMDD_HHMMSS.txt`:

```
=== GestureDog Session: 2026-04-05 14:32:01 ===
[14:32:05] CMD #1: WALK_FORWARD
[14:32:08] CMD #2: STOP
[14:32:10] AUTO-STOP
[14:32:15] CMD #3: JUMP
=== Session Ended: 2026-04-05 14:35:22 | Total: 3 cmds ===
```

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| Stream not connecting | `sudo fuser -k /dev/video0` then restart stream tmux |
| Robot not moving | Check `tmux attach -t recv` for serial errors |
| Robot not stopping | Show open palm or remove hand for 1 second |
| Gestures misdetected | Better lighting, plain background, hand 30-50cm away |
| Jump/Handshake incomplete | Trigger from standing still position |
| IP not found | Check router admin for MAC `88:a2:9e:22:fe:c4` |
| WiFi dropping | Run `sudo iw dev wlan0 set power_save off` on Pi |

---

## 🛑 Shutdown

### Laptop
Press `Q` in GestureDog window or `Ctrl+C`

### Pi
```bash
tmux kill-server
sudo shutdown now
```

---

## 🎓 Academic Context

**Concepts demonstrated:**
- Sense-Plan-Act cognitive architecture
- Symbol grounding via geometric landmark analysis
- Selective attention modeled through debouncing
- Reactive safety via auto-stop behavior
- Distributed computing — perception on laptop, actuation on embedded system

---

*Built with MediaPipe, OpenCV, Python, Raspberry Pi, and a lot of debugging 🐕*
