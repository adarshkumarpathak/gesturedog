import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, HandLandmarkerResult
from mediapipe import Image, ImageFormat
import socket
import time
import urllib.request
import numpy as np
from loguru import logger
from datetime import datetime
import os

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
PI_IP           = '10.141.192.172'
PI_CMD_PORT     = 9999
PI_STREAM_URL   = f'http://{PI_IP}:8080/stream'
MODEL_PATH      = r'D:\wavego\hand_landmarker.task'

DEBOUNCE_FRAMES = 7        # frames needed to confirm gesture
COOLDOWN_SEC    = 1.5      # min time between commands
AUTO_STOP_SEC   = 1.0      # stop robot after 1s no hand
CONFIDENCE_SEC  = 1.0      # confidence bar fills over 1 second

LOG_DIR  = r'D:\wavego\logs'
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f'session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')

# ─────────────────────────────────────────
# STATE
# ─────────────────────────────────────────
gesture_buffer    = []
last_command_time = 0
last_command      = None
last_hand_time    = time.time()
auto_stopped      = False
current_landmarks = None
command_count     = 0

# ─────────────────────────────────────────
# SESSION LOGGER
# ─────────────────────────────────────────
def log_session(entry):
    with open(LOG_FILE, 'a') as f:
        f.write(entry + '\n')

log_session(f"=== GestureDog Session: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

# ─────────────────────────────────────────
# MEDIAPIPE SETUP
# ─────────────────────────────────────────
def on_result(result: HandLandmarkerResult, output_image: Image, timestamp_ms: int):
    global current_landmarks, last_hand_time
    if result.hand_landmarks:
        current_landmarks = result.hand_landmarks[0]
        last_hand_time = time.time()
    else:
        current_landmarks = None

base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
options = HandLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    num_hands=1,
    min_hand_detection_confidence=0.75,
    min_hand_presence_confidence=0.75,
    min_tracking_confidence=0.6,
    result_callback=on_result
)
detector = HandLandmarker.create_from_options(options)

# ─────────────────────────────────────────
# GESTURE CLASSIFICATION
# ─────────────────────────────────────────
def get_finger_states(landmarks):
    fingers = []
    fingers.append(1 if landmarks[4].x < landmarks[3].x else 0)
    for tip, pip in [(8,6), (12,10), (16,14), (20,18)]:
        fingers.append(1 if landmarks[tip].y < landmarks[pip].y else 0)
    return fingers

def thumb_pointing_up(landmarks):
    return landmarks[4].y < landmarks[2].y

def classify_gesture(landmarks):
    f = get_finger_states(landmarks)

    if f == [1,1,1,1,1]: return 'STOP'
    if f == [0,0,0,0,0]: return 'STAND'
    if f == [0,1,0,0,0]: return 'WALK_FORWARD'
    if f == [0,1,1,0,0]: return 'WALK_BACKWARD'
    if f == [1,0,0,0,1]: return 'SPIN_LEFT'
    if f == [0,0,1,0,0]: return 'SPIN_RIGHT'
    if f == [0,1,1,1,0]: return 'JUMP'
    if f == [0,1,1,1,1]: return 'BALANCE'
    if f == [0,1,0,0,1]: return 'HANDSHAKE'
    if f == [1,0,0,0,0]: return 'LAY_LOW'
    return None
# ─────────────────────────────────────────
# COMMUNICATION
# ─────────────────────────────────────────
def send_command(sock, command):
    global last_command_time, last_command, command_count
    now = time.time()
    if command == last_command:
        return
    if now - last_command_time < COOLDOWN_SEC:
        return
    sock.send((command + '\n').encode())
    last_command      = command
    last_command_time = now
    command_count    += 1
    entry = f"[{datetime.now().strftime('%H:%M:%S')}] CMD #{command_count}: {command}"
    logger.info(entry)
    log_session(entry)

def connect_to_pi():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((PI_IP, PI_CMD_PORT))
    logger.info(f"Connected to Pi at {PI_IP}:{PI_CMD_PORT}")
    return s

# ─────────────────────────────────────────
# DRAW LANDMARKS WITH CONNECTIONS
# ─────────────────────────────────────────
def draw_landmarks(frame, landmarks):
    h, w = frame.shape[:2]
    connections = [
        (0,1),(1,2),(2,3),(3,4),
        (0,5),(5,6),(6,7),(7,8),
        (5,9),(9,10),(10,11),(11,12),
        (9,13),(13,14),(14,15),(15,16),
        (13,17),(17,18),(18,19),(19,20),
        (0,17)
    ]
    pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
    for a, b in connections:
        cv2.line(frame, pts[a], pts[b], (0, 200, 0), 2)
    for pt in pts:
        cv2.circle(frame, pt, 5, (0, 255, 0), -1)

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────
def main():
    global gesture_buffer, auto_stopped, last_hand_time

    logger.info("Connecting to Pi stream...")
    stream = urllib.request.urlopen(PI_STREAM_URL, timeout=30)
    logger.info("Stream connected!")
    sock = connect_to_pi()

    bytes_data = b''
    timestamp  = 0
    gesture_start_time = None
    last_gesture_seen  = None

    logger.info("GestureDog running! Show your hand.")
    log_session(f"Stream connected to {PI_STREAM_URL}")

    while True:
        try:
            chunk = stream.read(1024)
            bytes_data += chunk
            a     = bytes_data.find(b'\xff\xd8')
            b_end = bytes_data.find(b'\xff\xd9')

            if a == -1 or b_end == -1:
                continue

            jpg        = bytes_data[a:b_end+2]
            bytes_data = bytes_data[b_end+2:]

            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb)
            timestamp += 1
            detector.detect_async(mp_image, timestamp)

            gesture = None
            now     = time.time()

            if current_landmarks:
                draw_landmarks(frame, current_landmarks)
                gesture = classify_gesture(current_landmarks)
                auto_stopped = False

                # Track how long current gesture has been held
                if gesture == last_gesture_seen:
                    pass  # keep tracking
                else:
                    gesture_start_time = now
                    last_gesture_seen  = gesture

            else:
                gesture_start_time = None
                last_gesture_seen  = None

            # Auto STOP after 1s no hand
            if now - last_hand_time > AUTO_STOP_SEC and not auto_stopped:
                sock.send(('STOP\n').encode())
                auto_stopped = True
                entry = f"[{datetime.now().strftime('%H:%M:%S')}] AUTO-STOP"
                logger.info(entry)
                log_session(entry)

            # Debounce
            gesture_buffer.append(gesture)
            if len(gesture_buffer) > DEBOUNCE_FRAMES:
                gesture_buffer.pop(0)

            if len(gesture_buffer) == DEBOUNCE_FRAMES and \
               all(g == gesture_buffer[0] for g in gesture_buffer) and \
               gesture_buffer[0] is not None:
                send_command(sock, gesture_buffer[0])

            # Confidence bar — based on 1 second hold time
            conf_pct = 0
            if gesture and gesture_start_time:
                held = now - gesture_start_time
                conf_pct = min(held / CONFIDENCE_SEC, 1.0)

            bar_w = int(conf_pct * 200)
            bar_color = (0, 255, 0) if conf_pct >= 1.0 else (0, 165, 255)
            cv2.rectangle(frame, (10, frame.shape[0]-30),
                         (10 + bar_w, frame.shape[0]-10), bar_color, -1)
            cv2.rectangle(frame, (10, frame.shape[0]-30),
                         (210, frame.shape[0]-10), (255,255,255), 1)
            cv2.putText(frame, 'Hold to confirm', (215, frame.shape[0]-12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)

            # HUD
            cv2.putText(frame, f'Gesture: {gesture or "None"}',
                       (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
            cv2.putText(frame, f'Command: {last_command or "None"}',
                       (10, 60),  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
            cv2.putText(frame, f'Total:   {command_count} cmds',
                       (10, 90),  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200,200,200), 2)

            if not current_landmarks:
                no_hand_sec = round(now - last_hand_time, 1)
                cv2.putText(frame, f'No hand: {no_hand_sec}s',
                           (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

            cv2.imshow('GestureDog', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        except Exception as e:
            logger.error(f"Error: {e}")
            break

    cv2.destroyAllWindows()
    sock.close()
    log_session(f"=== Session Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Total: {command_count} cmds ===")
    logger.info(f"Log saved: {LOG_FILE}")

if __name__ == '__main__':
    while True:
        try:
            main()
        except Exception as e:
            logger.error(f"Crashed: {e}, restarting in 3s...")
            log_session(f"CRASH: {e}")
            time.sleep(3)