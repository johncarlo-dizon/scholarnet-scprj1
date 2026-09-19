import customtkinter as ctk
import json
import os
import socket
import threading
import datetime
import struct
import time
import cv2
import numpy as np
import pyautogui
from config import apply_theme
from teacher_dashboard.teacher_dash import TeacherDashboard
from teacher_dashboard.network_listeners import handle_student_expression
from teacher_dashboard.network_listeners import start_persistent_stream_listeners, update_student_card_name
from admin_dashboard.admin_dash import AdminDashboard
from database import db
apply_theme()
db.init_db()
db.seed_defaults()
from teacher_dashboard.teacher_screen_sender import start_teacher_streaming, stop_teacher_streaming
from ui_utils import center_window

class LabSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, on_selected):
        super().__init__(master)
        self.title("Select Computer Lab")
        center_window(self, 350, 220)
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        ctk.CTkLabel(self, text="Which lab are you in today?", font=("Arial", 16, "bold")).pack(pady=20)

        labs = db.get_all_labs()
        self.lab_map = {lab["name"]: lab["id"] for lab in labs}
        self.lab_dropdown = ctk.CTkOptionMenu(self, values=list(self.lab_map.keys()) or ["No labs found"], width=250)
        self.lab_dropdown.pack(pady=10)
        if self.lab_map:
            self.lab_dropdown.set(list(self.lab_map.keys())[0])

        ctk.CTkButton(self, text="Confirm", command=lambda: self._confirm(on_selected)).pack(pady=20)

    def _confirm(self, on_selected):
        selected = self.lab_dropdown.get()
        lab_id = self.lab_map.get(selected)
        if lab_id:
            self.destroy()
            on_selected(lab_id)


class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.init_db()
        db.seed_defaults()
        
        self.title("CompHub Login - Teacher/Admin")
        center_window(self, 700, 500)
        self.USERS = {
            "student": {"password": "student123", "role": "Student"},
            "teacher": {"password": "teacher123", "role": "Teacher"},
            "admin": {"password": "admin123", "role": "Admin"}
        }
        
        self.all_logs = [] 
        self.active_sessions = {} 
        self.active_broadcast = False
        self.broadcast_socket = None
        self.active_teacher_dashboard = None  # <--- Reference para sa student expressions
        self.login_history_data = []

    
        start_persistent_stream_listeners(self)
        
        # Simulan ang background log listener at broadcast server
        threading.Thread(target=self.start_log_listener, daemon=True).start()
        threading.Thread(target=self.broadcast_stream_server, daemon=True).start()
        
        ctk.CTkLabel(self, text="CompHub Login", font=("Arial", 20, "bold")).pack(pady=20)

        self.user_entry = ctk.CTkEntry(self, placeholder_text="Username")
        self.user_entry.pack(pady=10)
        self.pass_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*")
        self.pass_entry.pack(pady=10)
        self.btn_login = ctk.CTkButton(self, text="Login", command=self.check_login)
        self.btn_login.pack(pady=20)
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack()

    def start_log_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", 5001))
        server.listen(5)
        print("==========================================")
        print("[DEBUG] Log & Command listener ay BUKAS sa port 5001")
        print("==========================================")
        while True:
            try:
                conn, addr = server.accept()
                data = conn.recv(2048).decode('utf-8', errors='ignore').strip()
                
                if "ACTION: LOGIN_CHECK" in data:
                    self.handle_login_check(conn, data)
                elif "ACTION: GET_TEACHERS" in data:
                    self.handle_get_teachers(conn)
                elif "ACTION: GET_LABS" in data:
                    self.handle_get_labs(conn)
                elif "ACTION: SET_LAB" in data:
                    self.handle_set_lab(conn, data)
                elif "ACTION: GET_HISTORY" in data:
                    self.handle_get_history(conn, data)
                elif "ACTION: CHANGE_PWD" in data:
                    self.handle_change_password(conn, data)
                elif "ACTION: REGISTER" in data:
                    self.process_register(data)
                    conn.close()
                elif "ACTION: LOGIN" in data:
                    self.handle_student_login_event(data, addr)
                    conn.close()
                elif "ACTION: LOGOUT" in data:
                    self.handle_student_logout_event(data)
                elif "ACTION: GET_BLOCKLIST" in data:
                    self.handle_get_blocklist(conn)
                elif "ACTION: SITE_ALERT" in data:
                    self.handle_site_alert(data)
                    conn.close()

                elif "EXPRESSION:" in data:
                    expr_content = data.replace("EXPRESSION:", "").strip()
                    print(f"[STUDENT EXPRESSION] mula {addr[0]}: {expr_content}")
                    
                    if self.active_teacher_dashboard:
                        if not hasattr(self.active_teacher_dashboard, 'inbox_logs_data'):
                            self.active_teacher_dashboard.inbox_logs_data = []
                            
                        new_log = {
                            "time": datetime.datetime.now().strftime('%H:%M:%S'),
                            "message": f"[{addr[0]}] Expression: {expr_content}"
                        }
                        self.active_teacher_dashboard.inbox_logs_data.append(new_log)
                        
                        # I-refresh ang UI ng Inbox at Student Card nang sabay
                        self.active_teacher_dashboard.after(
                            0, lambda: self.active_teacher_dashboard.refresh_inbox_ui()
                        )
                        self.active_teacher_dashboard.after(
                            0, lambda e=expr_content, ip=addr[0]: handle_student_expression(self.active_teacher_dashboard, e, ip)
                        )
                    conn.close()
                else:
                    self.process_log(data)
                    conn.close()
            except: 
                break

    def handle_login_check(self, conn, data):
        try:
            parts = data.split("|")
            username = ""
            password = ""
            teacher_id_str = ""
            lab_id_str = ""
            for part in parts:
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()
                elif "PWD:" in part:
                    password = part.split("PWD:")[1].strip()
                elif "TEACHERID:" in part:
                    teacher_id_str = part.split("TEACHERID:")[1].strip()
                elif "LABID:" in part:
                    lab_id_str = part.split("LABID:")[1].strip()

            user = db.verify_password(username, password)
            if not user or user["role"] != "student":
                conn.send("FAILED".encode())
                return

            selected_teacher_id = int(teacher_id_str) if teacher_id_str.isdigit() else None
            selected_lab_id = int(lab_id_str) if lab_id_str.isdigit() else None

            active_teacher_id = getattr(self, "current_teacher_user_id", None)
            active_lab_id = getattr(self, "current_teacher_lab_id", None)

            if active_teacher_id is None:
                conn.send("TEACHER_OFFLINE".encode())
                return

            if selected_teacher_id != active_teacher_id or selected_lab_id != active_lab_id:
                conn.send("LAB_MISMATCH".encode())
                return

            db.set_user_lab(user["id"], selected_lab_id)
            conn.send("SUCCESS".encode())
        except Exception as e:
            print(f"[ERROR sa login check]: {e}")
            conn.send("FAILED".encode())
        finally:
            conn.close()

    def handle_get_blocklist(self, conn):
        try:
            blocklist = db.get_blocklist()
            conn.send(json.dumps(blocklist).encode())
        except Exception as e:
            print(f"[ERROR sa get_blocklist]: {e}")
            conn.send(json.dumps([]).encode())
        finally:
            conn.close()

    def handle_site_alert(self, data):
        try:
            username = text = category = ""
            for part in data.split("|"):
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()
                elif "TEXT:" in part:
                    text = part.split("TEXT:")[1].strip()
                elif "CATEGORY:" in part:
                    category = part.split("CATEGORY:")[1].strip()

            user = db.get_user_by_username(username)
            if not user:
                return
            session_id = db.get_active_session_id(user["id"])
            db.log_site_alert(user["id"], session_id, text, category)

            dashboard = self.active_teacher_dashboard
            if dashboard and hasattr(dashboard, 'refresh_inbox_ui'):
                self.after(0, dashboard.refresh_inbox_ui)
        except Exception as e:
            print(f"[ERROR sa site_alert]: {e}")

    def handle_change_password(self, conn, data):
        try:
            parts = data.split("|")
            username = old_pwd = new_pwd = ""
            for part in parts:
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()
                elif "OLDPWD:" in part:
                    old_pwd = part.split("OLDPWD:")[1].strip()
                elif "NEWPWD:" in part:
                    new_pwd = part.split("NEWPWD:")[1].strip()

            ok, msg = db.change_password(username, old_pwd, new_pwd)
            conn.send(("SUCCESS" if ok else "FAILED").encode())
        except Exception as e:
            print(f"[ERROR sa change_password]: {e}")
            conn.send("FAILED".encode())
        finally:
            conn.close()


    def handle_student_login_event(self, data, addr):
        try:
            username = ""
            for part in data.split("|"):
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()

            user = db.get_user_by_username(username)
            if user:
                session_id = db.start_session(
                    user["id"], lab_id=user.get("lab_id"),
                    pc_name=addr[0], ip_address=addr[0]
                )
                self.active_sessions[username] = session_id
        except Exception as e:
            print(f"[ERROR sa login event]: {e}")

    def handle_student_logout_event(self, data):
        try:
            username = ""
            for part in data.split("|"):
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()

            session_id = self.active_sessions.pop(username, None)
            if session_id is None:
                user = db.get_user_by_username(username)
                if user:
                    session_id = db.get_active_session_id(user["id"])
            if session_id:
                db.end_session(session_id)
        except Exception as e:
            print(f"[ERROR sa logout event]: {e}")

    def handle_get_history(self, conn, data):
        try:
            username = ""
            for part in data.split("|"):
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()

            user = db.get_user_by_username(username)
            if not user:
                conn.send(json.dumps([]).encode())
                return

            sessions = db.get_history_for_user(user["id"])
            teachers = db.get_teachers_for_student(user["id"])
            teacher_names = ", ".join(t["full_name"] or t["username"] for t in teachers) or "N/A"

            payload = [
                {
                    "login_time": s["login_time"],
                    "logout_time": s["logout_time"] or "Still active",
                    "duration_secs": s["duration_secs"] or 0,
                    "lab_name": s["lab_name"] or "N/A",
                    "teacher": teacher_names,
                }
                for s in sessions
            ]
            conn.send(json.dumps(payload).encode())
        except Exception as e:
            print(f"[ERROR sa get_history]: {e}")
            conn.send(json.dumps([]).encode())
        finally:
            conn.close()


    def handle_get_teachers(self, conn):
        try:
            teachers = db.get_all_teachers()
            payload = [
                {"id": t["id"], "username": t["username"], "full_name": t["full_name"] or t["username"]}
                for t in teachers
            ]
            conn.send(json.dumps(payload).encode())
        except Exception as e:
            print(f"[ERROR sa get_teachers]: {e}")
            conn.send(json.dumps([]).encode())
        finally:
            conn.close()

    def handle_get_labs(self, conn):
        try:
            labs = db.get_all_labs()
            conn.send(json.dumps(labs).encode())
        except Exception as e:
            print(f"[ERROR sa get_labs]: {e}")
            conn.send(json.dumps([]).encode())
        finally:
            conn.close()

    def handle_set_lab(self, conn, data):
        try:
            username = ""
            lab_id_str = ""
            for part in data.split("|"):
                if "USER:" in part:
                    username = part.split("USER:")[1].strip()
                elif "LABID:" in part:
                    lab_id_str = part.split("LABID:")[1].strip()

            user = db.get_user_by_username(username)
            if user and lab_id_str.isdigit():
                db.set_user_lab(user["id"], int(lab_id_str))
                conn.send("SUCCESS".encode())

                # If this student is already connected/visible, re-check visibility now
                ip_to_username = getattr(self, "ip_to_username", {})
                for ip, uname in list(ip_to_username.items()):
                    if uname == username:
                        self.after(0, lambda u=username, i=ip: update_student_card_name(self, u, i))
            else:
                conn.send("FAILED".encode())
        except Exception as e:
            print(f"[ERROR sa set_lab]: {e}")
            conn.send("FAILED".encode())
        finally:
            conn.close()

    def process_register(self, data):
        try:
            parts = data.split("|")
            fields = {}
            for part in parts:
                if ":" in part:
                    key, val = part.split(":", 1)
                    fields[key.strip()] = val.strip()

            teacher_id_str = fields.get("TEACHERID", "")
            teacher_ids = [int(teacher_id_str)] if teacher_id_str.isdigit() else []

            ok, result = db.register_student(
                username=fields.get("USER", ""),
                password=fields.get("PWD", ""),
                full_name=fields.get("FULLNAME", ""),
                school_id=fields.get("SCHOOLID", ""),
                email=fields.get("EMAIL", ""),
                contact_number=fields.get("CONTACT", ""),
                course_section=fields.get("COURSE", ""),
                year_level=fields.get("YEAR", ""),
                teacher_ids=teacher_ids,
            )
            if ok:
                print(f"[SUCCESS] Na-save sa database, naghihintay ng approval! (user id {result})")
            else:
                print(f"[FAILED] Registration error: {result}")
        except Exception as e:
            print(f"[ERROR sa pag-save ng registration]: {e}")

    def process_log(self, data):
        try:
            parts = {p.split(": ")[0].strip(): p.split(": ")[1].strip() for p in data.split(" | ")}
            action, user, time_str = parts.get("ACTION"), parts.get("USER"), parts.get("TIME")
            if action == "LOGIN":
                self.all_logs.append({"user": user, "login": time_str, "logout": "--", "duration": "--"})
            elif action == "LOGOUT":
                for entry in reversed(self.all_logs):
                    if entry['user'] == user and entry['logout'] == "--":
                        login_dt = datetime.datetime.strptime(entry['login'], "%H:%M:%S")
                        logout_dt = datetime.datetime.strptime(time_str, "%H:%M:%S")
                        entry.update({"logout": time_str, "duration": str(logout_dt - login_dt)})
                        break
        except: pass

    # --- FULL SCREEN DEMO BROADCAST SERVER ---
    def broadcast_stream_server(self):
        PORT = 9996
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("0.0.0.0", PORT))
            server.listen(10)
            self.broadcast_socket = server
            print(f"[DEBUG] Broadcast Stream Server ay aktibo sa port {PORT}")
        except Exception as e:
            print(f"[ERROR sa Broadcast Server]: {e}")
            return
        
        while True:
            try:
                server.settimeout(1.0)
                conn, addr = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                threading.Thread(target=self.stream_handler, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except:
                break

    def stream_handler(self, conn):
        self.active_broadcast = True
        while self.active_broadcast:
            try:
                screenshot = pyautogui.screenshot()
                frame = np.array(screenshot)
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                frame = cv2.resize(frame, (1280, 720), interpolation=cv2.INTER_AREA)
                
                _, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
                data = encoded.tobytes()
                
                header = struct.pack("!I", len(data))
                conn.sendall(header + data)
                
                time.sleep(0.03)
            except:
                break
        try:
            conn.close()
        except:
            pass

    def check_login(self):
        username = self.user_entry.get()
        password = self.pass_entry.get()
        user = db.verify_password(username, password)
        if user and user["role"] in ("teacher", "admin"):
            self.withdraw()
            role = user["role"]

            if role == "teacher":
                def proceed_with_lab(lab_id):
                    db.set_user_lab(user["id"], lab_id)
                    self.current_teacher_lab_id = lab_id
                    self.current_teacher_user_id = user["id"]
                    dashboard = TeacherDashboard(master_app=self)
                    self.active_teacher_dashboard = dashboard
                    dashboard.protocol("WM_DELETE_WINDOW", lambda: self.on_dashboard_close(dashboard))
                    start_teacher_streaming(user["full_name"] or user["username"])

                LabSelectionDialog(self, proceed_with_lab)

            elif role == "admin":
                dashboard = AdminDashboard(master_app=self)
                self.active_teacher_dashboard = dashboard
                dashboard.protocol("WM_DELETE_WINDOW", lambda: self.on_dashboard_close(dashboard))
        else:
            self.error_label.configure(text="Invalid credentials!", text_color="red")

    def on_dashboard_close(self, dashboard):
        if dashboard == self.active_teacher_dashboard:
            self.active_teacher_dashboard = None
            if isinstance(dashboard, TeacherDashboard):
                self.current_teacher_lab_id = None
                self.current_teacher_user_id = None
                stop_teacher_streaming()
        dashboard.destroy()
        self.deiconify()

if __name__ == "__main__":
    app = LoginApp()
    app.mainloop()