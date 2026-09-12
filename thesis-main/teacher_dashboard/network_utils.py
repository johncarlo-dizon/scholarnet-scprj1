# network_utils.py
import socket
from network_config import COMMAND_PORT, CONTROL_PORT

def send_command(target_student_ip, command):
    """Para sa LOCK/UNLOCK (Port 5000)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2) 
            s.connect((target_student_ip, COMMAND_PORT))
            s.sendall(command.encode()) # Tinanggal ang \n para tumugma sa student[cite: 5]
            print(f"Command '{command}' sent to {target_student_ip}")
    except Exception as e:
        print(f"Hindi makakonekta sa student PC {target_student_ip}: {e}")

def send_control_command(target_ip, command):
    """Para sa Control Commands (Port 9999)[cite: 5]"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((target_ip, CONTROL_PORT))
            s.sendall(f"{command}\n".encode())
            print(f"Control command '{command}' sent to {target_ip}")
    except Exception as e:
        print(f"Control command error: {e}")