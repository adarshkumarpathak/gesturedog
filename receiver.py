import socket
import serial
import json
import time
from loguru import logger

SERIAL_PORT = '/dev/serial0'
SERIAL_BAUD = 115200
HOST        = '0.0.0.0'
PORT        = 9999

try:
    ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
    logger.info(f"Serial connected on {SERIAL_PORT}")
except Exception as e:
    logger.error(f"Serial failed: {e}")
    ser = None

def send_raw(cmd_dict):
    if ser:
        cmd = json.dumps(cmd_dict)
        ser.write(cmd.encode())
        time.sleep(0.05)

def stop_robot():
    send_raw({'var': 'move', 'val': 3})
    send_raw({'var': 'move', 'val': 6})

def send_to_robot(command):
    if command in ('STOP', 'STAND'):
        stop_robot()
        logger.info("FULL STOP")

    elif command == 'WALK_FORWARD':
        send_raw({'var': 'move', 'val': 1})

    elif command == 'WALK_BACKWARD':
        send_raw({'var': 'move', 'val': 5})

    elif command == 'SPIN_LEFT':
        send_raw({'var': 'move', 'val': 2})

    elif command == 'SPIN_RIGHT':
        send_raw({'var': 'move', 'val': 4})

    elif command == 'JUMP':
        # Stop first then jump
        stop_robot()
        time.sleep(0.3)
        send_raw({'var': 'funcMode', 'val': 4})

    elif command == 'LAY_LOW':
        # Stop first then lay low
        stop_robot()
        time.sleep(0.3)
        send_raw({'var': 'funcMode', 'val': 2})

    elif command == 'BALANCE':
        stop_robot()
        time.sleep(0.3)
        send_raw({'var': 'funcMode', 'val': 1})

    elif command == 'HANDSHAKE':
        # Stop first then handshake
        stop_robot()
        time.sleep(0.3)
        send_raw({'var': 'funcMode', 'val': 3})

    else:
        logger.warning(f"Unknown command: {command}")

    logger.info(f"Executed: {command}")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(5)
logger.info(f"Receiver listening on port {PORT}...")

while True:
    try:
        conn, addr = server.accept()
        logger.info(f"Laptop connected from {addr}")
        while True:
            data = conn.recv(1024).decode().strip()
            if not data:
                break
            logger.info(f"Received: {data}")
            send_to_robot(data)
        conn.close()
    except Exception as e:
        logger.error(f"Connection error: {e}")
        time.sleep(1)
