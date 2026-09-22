import customtkinter as ctk
import socket
import threading
import json
import os
import webbrowser
import struct
import cv2
import time
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk
import screen_sender
from student_webcam_window import StudentWebcamOverlay
import pygetwindow as gw
from ui_utils import center_window
from network_config import TEACHER_IP, LOG_PORT, LISTENER_PORT, BROADCAST_PORT, ADMIN_IP
USER_FILE = "users.json"

class LockScreen(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.title("Terminal Locked")
        ctk.CTkLabel(self, text="TERMINAL LOCKED", font=("Arial", 60, "bold"), text_color="red").pack(expand=True)


class TeacherPOVViewer(ctk.CTkToplevel):
    """Shown to a student only while the teacher is actively Remote
    Controlling them. Displays the teacher's live screen. Not closable by
    the student, and excluded from Alt+Tab via overrideredirect."""
    def __init__(self, master, teacher_ip, broadcast_port):
        super().__init__(master)
        self.teacher_ip = teacher_ip
        self.broadcast_port = broadcast_port
        self.overrideredirect(True)  # no window frame -> not in Alt+Tab switcher
        self.attributes("-topmost", True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

        self.label = tk.Label(self, bg="black")
        self.label.pack(fill="both", expand=True)

        self.latest_image = None
        self._frame_pending = False
        self.running = True
        self._sock = None

        self._refocus_loop()
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _refocus_loop(self):
        if not self.running:
            return
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self.after(500, self._refocus_loop)

    def _receive_loop(self):
        while self.running:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._sock.connect((self.teacher_ip, self.broadcast_port))

                while self.running:
                    header = self._sock.recv(4)
                    if not header:
                        break
                    frame_length = struct.unpack("!I", header)[0]

                    data = bytearray()
                    while len(data) < frame_length:
                        packet = self._sock.recv(frame_length - len(data))
                        if not packet:
                            break
                        data.extend(packet)

                    if len(data) == frame_length and self.running:
                        self.after(0, lambda d=bytes(data): self._update_frame(d))
            except Exception:
                time.sleep(1)
            finally:
                try:
                    if self._sock:
                        self._sock.close()
                except Exception:
                    pass

    def _update_frame(self, data):
        if self._frame_pending or not self.running:
            return
        self._frame_pending = True
        try:
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame)
                new_w = self.label.winfo_width()
                new_h = self.label.winfo_height()
                if new_w > 10 and new_h > 10:
                    image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
                photo = ImageTk.PhotoImage(image)
                self.label.config(image=photo)
                self.label.image = photo
        except Exception as e:
            print(f"[ERROR TeacherPOVViewer frame]: {e}")
        finally:
            self._frame_pending = False

    def close_pov(self):
        self.running = False
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

class DemoViewer(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

        self.video_label = tk.Label(self, bg="black")
        self.video_label.pack(fill="both", expand=True)

        self.latest_image = None
        self._frame_pending = False
        self.running = True

        self._refocus_loop()

    def _refocus_loop(self):
        if not self.running:
            return
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self.after(500, self._refocus_loop)

    def update_frame(self, data):
        if self._frame_pending or not self.running:
            return
        self._frame_pending = True
        try:
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame)
                self.latest_image = image

                new_w = self.video_label.winfo_width()
                new_h = self.video_label.winfo_height()
                if new_w > 10 and new_h > 10:
                    image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

                photo = ImageTk.PhotoImage(image)
                self.video_label.config(image=photo)
                self.video_label.image = photo
        except Exception as e:
            print(f"Error sa pag-update ng live demo frame: {e}")
        finally:
            self._frame_pending = False

    def close_demo(self):
        self.running = False
        try:
            self.destroy()
        except Exception:
            pass

class RegisterWindow(ctk.CTkToplevel):
    def __init__(self, master, teacher_ip, log_port):
        super().__init__(master)
        self.teacher_ip = teacher_ip
        self.log_port = log_port
        self.title("Student Registration")
        center_window(self, 400, 680)
        self.transient(master)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        ctk.CTkLabel(self, text="Create Student Account", font=("Arial", 20, "bold")).pack(pady=20)

        self.user_entry = ctk.CTkEntry(self, placeholder_text="Username", width=300)
        self.user_entry.pack(pady=5)
        self.pass_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=300)
        self.pass_entry.pack(pady=5)
        self.repass_entry = ctk.CTkEntry(self, placeholder_text="Re-type Password", show="*", width=300)
        self.repass_entry.pack(pady=5)
        self.fullname_entry = ctk.CTkEntry(self, placeholder_text="Full Name", width=300)
        self.fullname_entry.pack(pady=5)
        self.schoolid_entry = ctk.CTkEntry(self, placeholder_text="School ID Number", width=300)
        self.schoolid_entry.pack(pady=5)
        self.email_entry = ctk.CTkEntry(self, placeholder_text="Email", width=300)
        self.email_entry.pack(pady=5)
        self.contact_entry = ctk.CTkEntry(self, placeholder_text="Contact Number", width=300)
        self.contact_entry.pack(pady=5)
        self.course_entry = ctk.CTkEntry(self, placeholder_text="Course & Section", width=300)
        self.course_entry.pack(pady=5)
        self.year_entry = ctk.CTkEntry(self, placeholder_text="Year Level", width=300)
        self.year_entry.pack(pady=5)

        ctk.CTkLabel(self, text="Select your Teacher:").pack(pady=(10, 0))
        self.teacher_map = {}
        self.teacher_dropdown = ctk.CTkOptionMenu(self, values=["Loading..."], width=300)
        self.teacher_dropdown.pack(pady=5)
        self.after(100, self.fetch_teachers)

        ctk.CTkButton(self, text="Submit Registration", fg_color="green", command=self.submit_reg).pack(pady=20)
        self.status_lbl = ctk.CTkLabel(self, text="", text_color="white", wraplength=350)
        self.status_lbl.pack()

        self.lift()
        self.focus_force()
        self.grab_set()

    def close_window(self):
        self.grab_release()
        self.destroy()

    def fetch_teachers(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((self.teacher_ip, self.log_port))
            client.send("ACTION: GET_TEACHERS".encode())
            response = client.recv(4096).decode()
            client.close()

            teachers = json.loads(response)
            if teachers:
                self.teacher_map = {f"{t['full_name']} ({t['username']})": t["id"] for t in teachers}
                self.teacher_dropdown.configure(values=list(self.teacher_map.keys()))
                self.teacher_dropdown.set(list(self.teacher_map.keys())[0])
            else:
                self.teacher_dropdown.configure(values=["No teachers available"])
                self.teacher_dropdown.set("No teachers available")
        except Exception as e:
            self.teacher_dropdown.configure(values=["Connection failed"])
            self.teacher_dropdown.set("Connection failed")
            print(f"[ERROR fetch_teachers]: {e}")

    def submit_reg(self):
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()
        repwd = self.repass_entry.get().strip()
        full_name = self.fullname_entry.get().strip()
        school_id = self.schoolid_entry.get().strip()
        email = self.email_entry.get().strip()
        contact = self.contact_entry.get().strip()
        course = self.course_entry.get().strip()
        year = self.year_entry.get().strip()
        selected_teacher = self.teacher_dropdown.get()

        required = [user, pwd, repwd, full_name, school_id, email, contact, course, year]
        if not all(required):
            self.status_lbl.configure(text="Punan ang lahat ng kahon.", text_color="orange")
            return

        if pwd != repwd:
            self.status_lbl.configure(text="Hindi magkatugma ang password.", text_color="orange")
            return

        teacher_id = self.teacher_map.get(selected_teacher)
        if not teacher_id:
            self.status_lbl.configure(text="Pumili ng valid na teacher.", text_color="orange")
            return

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.teacher_ip, self.log_port))
            msg = (
                f"ACTION: REGISTER | USER: {user} | PWD: {pwd} | FULLNAME: {full_name} | "
                f"SCHOOLID: {school_id} | EMAIL: {email} | CONTACT: {contact} | "
                f"COURSE: {course} | YEAR: {year} | TEACHERID: {teacher_id}"
            )
            client.send(msg.encode())
            client.close()
            self.status_lbl.configure(text="Naipadala na! Maghintay ng approval.", text_color="green")
        except Exception as e:
            self.status_lbl.configure(text=f"Nabigo ang koneksyon: {e}", text_color="red")


class LabSelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, teacher_ip, log_port, username, on_selected):
        super().__init__(master)
        self.teacher_ip = teacher_ip
        self.log_port = log_port
        self.username = username
        self.on_selected = on_selected
        self.title("Select Computer Lab")
        self.geometry("350x220")
        self.attributes("-topmost", True)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # must pick a lab, can't just close this
        self.bind_all("<Control-Shift-F4>", lambda e: self.destroy())
        self.focus_force()

        ctk.CTkLabel(self, text="Which lab are you in?", font=("Arial", 16, "bold")).pack(pady=20)

        self.lab_map = {}
        self.lab_dropdown = ctk.CTkOptionMenu(self, values=["Loading..."], width=250)
        self.lab_dropdown.pack(pady=10)
        self.after(100, self.fetch_labs)

        ctk.CTkButton(self, text="Confirm", command=self.confirm).pack(pady=20)
        self.status_lbl = ctk.CTkLabel(self, text="", text_color="red")
        self.status_lbl.pack()

    def fetch_labs(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((self.teacher_ip, self.log_port))
            client.send("ACTION: GET_LABS".encode())
            response = client.recv(4096).decode()
            client.close()

            labs = json.loads(response)
            if labs:
                self.lab_map = {lab["name"]: lab["id"] for lab in labs}
                self.lab_dropdown.configure(values=list(self.lab_map.keys()))
                self.lab_dropdown.set(list(self.lab_map.keys())[0])
            else:
                self.lab_dropdown.configure(values=["No labs found"])
        except Exception as e:
            self.lab_dropdown.configure(values=["Connection failed"])
            print(f"[ERROR fetch_labs]: {e}")

    def confirm(self):
        selected = self.lab_dropdown.get()
        lab_id = self.lab_map.get(selected)
        if not lab_id:
            self.status_lbl.configure(text="Please wait for labs to load.")
            return
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((self.teacher_ip, self.log_port))
            client.send(f"ACTION: SET_LAB | USER: {self.username} | LABID: {lab_id}".encode())
            client.recv(1024)
            client.close()
        except Exception as e:
            print(f"[ERROR set_lab]: {e}")

        self.destroy()
        self.on_selected()

class StudentDashboard(ctk.CTkToplevel):
    def __init__(self, username, master_app):
        super().__init__()
        self.username = username
        self.master_app = master_app
        self.title(f"Student Portal - {self.username}")
        center_window(self, 500, 450)
        
        tabview = ctk.CTkTabview(self)
        tabview.pack(expand=True, fill="both", padx=20, pady=20)
        tabview.add("My Account")
        tabview.add("History")
        tabview.add("Settings")
        
        ctk.CTkLabel(tabview.tab("My Account"), text=f"Welcome, {self.username}").pack(pady=20)
        ctk.CTkButton(tabview.tab("My Account"), text="Logout", fg_color="red", command=self.logout).pack(pady=10)
        history_frame = ctk.CTkScrollableFrame(tabview.tab("History"), width=440, height=300)
        history_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.history_frame = history_frame
        ctk.CTkButton(tabview.tab("History"), text="Refresh History", command=self.load_history).pack(pady=5)
        self.after(200, self.load_history)
        
        self.old_p = ctk.CTkEntry(tabview.tab("Settings"), placeholder_text="Old Password", show="*")
        self.old_p.pack(pady=5)
        self.new_p = ctk.CTkEntry(tabview.tab("Settings"), placeholder_text="New Password", show="*")
        self.new_p.pack(pady=5)
        self.re_p = ctk.CTkEntry(tabview.tab("Settings"), placeholder_text="Re-type New", show="*")
        self.re_p.pack(pady=5)
        ctk.CTkButton(tabview.tab("Settings"), text="Update Password", command=self.change_password).pack(pady=10)
        self.msg = ctk.CTkLabel(tabview.tab("Settings"), text="")    
        self.msg.pack()

    def change_password(self):
        old_pwd = self.old_p.get().strip()
        new_pwd = self.new_p.get().strip()
        re_pwd = self.re_p.get().strip()

        if not old_pwd or not new_pwd or not re_pwd:
            self.msg.configure(text="Punan ang lahat ng kahon.", text_color="orange")
            return
        if new_pwd != re_pwd:
            self.msg.configure(text="Hindi magkatugma ang bagong password.", text_color="red")
            return

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ADMIN_IP, LOG_PORT))
            msg = f"ACTION: CHANGE_PWD | USER: {self.username} | OLDPWD: {old_pwd} | NEWPWD: {new_pwd}"
            client.send(msg.encode())
            response = client.recv(1024).decode().strip()
            client.close()

            if response == "SUCCESS":
                self.msg.configure(text="Success!", text_color="green")
            else:
                self.msg.configure(text="Wrong current password!", text_color="red")
        except Exception as e:
            self.msg.configure(text=f"Connection error: {e}", text_color="red")

    def load_history(self):
        for widget in self.history_frame.winfo_children():
            widget.destroy()

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((ADMIN_IP, LOG_PORT))
            client.send(f"ACTION: GET_HISTORY | USER: {self.username}".encode())
            response = client.recv(8192).decode()
            client.close()

            records = json.loads(response)
            if not records:
                ctk.CTkLabel(self.history_frame, text="No history yet.", text_color="gray").pack(pady=10)
                return

            for r in records:
                mins, secs = divmod(r["duration_secs"], 60)
                hrs, mins = divmod(mins, 60)
                duration_str = f"{hrs}h {mins}m {secs}s"
                text = (
                    f"Teacher: {r['teacher']}\n"
                    f"Lab: {r['lab_name']}\n"
                    f"Login: {r['login_time']}   Logout: {r['logout_time']}\n"
                    f"Duration: {duration_str}"
                )
                frm = ctk.CTkFrame(self.history_frame)
                frm.pack(fill="x", padx=5, pady=5)
                ctk.CTkLabel(frm, text=text, justify="left", anchor="w").pack(fill="x", padx=10, pady=8)
        except Exception as e:
            ctk.CTkLabel(self.history_frame, text=f"Error loading history: {e}", text_color="red").pack(pady=10)

    def logout(self):
        session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_session.json")
        if os.path.exists(session_path):
            try:
                os.remove(session_path)
            except:
                pass
        
        if hasattr(self.master_app, 'webcam_overlay') and self.master_app.webcam_overlay:
            self.master_app.webcam_overlay.close_camera()
            self.master_app.webcam_overlay = None

        self.master_app.notify_teacher("LOGOUT", self.username)
        self.destroy()
        self.master_app.deiconify()        
        self.master_app.after(100, self.master_app.fetch_teachers_and_labs)

class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Student Login")
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None) 
        
        self.active_lock = None
        self.demo_window = None
        self.webcam_overlay = None
        self.in_demo_mode = False
        self.load_users()
        self.blocklist_cache = []
        threading.Thread(target=self.fetch_blocklist, daemon=True).start()
        
        threading.Thread(target=self.start_server, daemon=True).start()
        threading.Thread(target=self.start_broadcast_listener, daemon=True).start()
        threading.Thread(target=screen_sender.start_control_listener, daemon=True).start()
        threading.Thread(target=self.track_active_window, daemon=True).start()
        
        ctk.CTkLabel(self, text="CompHub Login", font=("Arial", 25, "bold")).pack(pady=20)

        ctk.CTkLabel(self, text="Select Teacher:").pack()
        self.teacher_map = {}
        self.teacher_dropdown = ctk.CTkOptionMenu(self, values=["Loading..."], width=250)
        self.teacher_dropdown.pack(pady=(0, 10))

        ctk.CTkLabel(self, text="Select Computer Lab:").pack()
        self.lab_map = {}
        self.lab_dropdown = ctk.CTkOptionMenu(self, values=["Loading..."], width=250)
        self.lab_dropdown.pack(pady=(0, 15))

        self.after(100, self.fetch_teachers_and_labs)

        self.user_entry = ctk.CTkEntry(self, placeholder_text="Username")
        self.user_entry.pack(pady=10)
        self.pass_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*")
        self.pass_entry.pack(pady=10)

        ctk.CTkButton(self, text="Login", command=self.check_login).pack(pady=10)
        
        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack(pady=5)
        
        ctk.CTkButton(self, text="Create an Account", fg_color="transparent", text_color="#1f6aa5", 
                      command=lambda: RegisterWindow(self, ADMIN_IP, LOG_PORT)).pack(pady=5)

    def load_users(self):
        if os.path.exists(USER_FILE):
            with open(USER_FILE, "r") as f:
                self.USERS = json.load(f)
        else:
            self.USERS = {"student": {"password": "student123", "role": "Student"}}
            self.save_users()

    def save_users(self):
        with open(USER_FILE, "w") as f:
            json.dump(self.USERS, f)

    def track_active_window(self):
        last_window = ""
        while True:
            try:
                active_win = gw.getActiveWindow()
                if active_win and active_win.title:
                    current_window = active_win.title
                    if current_window != last_window and current_window.strip() != "":
                        last_window = current_window

                        username_val = "Student"
                        session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_session.json")
                        if os.path.exists(session_path):
                            try:
                                with open(session_path, "r") as sf:
                                    username_val = json.load(sf).get("username", "Student")
                            except:
                                pass
                        else:
                            try:
                                val = self.user_entry.get().strip()
                                if val:
                                    username_val = val
                            except:
                                pass

                        for entry in self.blocklist_cache:
                            if entry["keyword"].lower() in current_window.lower():
                                alert_msg = f"ACTION: SITE_ALERT | USER: {username_val} | TEXT: {current_window} | CATEGORY: {entry['category']}"
                                try:
                                    a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                    a.connect((ADMIN_IP, LOG_PORT))
                                    a.sendall(alert_msg.encode())
                                    a.close()
                                except Exception:
                                    pass
                                self.after(0, lambda t=current_window, c=entry["category"]: self.show_restricted_warning(t, c))
                                break

                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.connect((TEACHER_IP, LOG_PORT))
                        message = f"ACTIVITY: {socket.gethostname()} ({username_val}) - {current_window}"
                        s.sendall(message.encode('utf-8'))
                        s.close()
                        print(f"[DEBUG STUDENT ACTIVITY] Matagumpay na na-send: {message}")
            except Exception as e:
                print(f"[DEBUG STUDENT ACTIVITY ERROR]: {e}")
            time.sleep(3)



    def _open_pov_viewer(self):
        if self.pov_viewer and self.pov_viewer.winfo_exists():
            return
        self.pov_viewer = TeacherPOVViewer(self, TEACHER_IP, BROADCAST_PORT)

    def _close_pov_viewer(self):
        if self.pov_viewer:
            self.pov_viewer.close_pov()
            self.pov_viewer = None        

    def start_broadcast_listener(self):
        while True:
            while not self.in_demo_mode:
                time.sleep(0.2)
                
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                s.connect((TEACHER_IP, BROADCAST_PORT))
                
                while self.in_demo_mode:
                    header = s.recv(4)
                    if not header:
                        break
                    frame_length = struct.unpack("!I", header)[0]
                    
                    data = bytearray()
                    while len(data) < frame_length:
                        packet = s.recv(frame_length - len(data))
                        if not packet:
                            break
                        data.extend(packet)
                    
                    if len(data) == frame_length and self.demo_window and self.demo_window.winfo_exists():
                        self.after(0, lambda d=bytes(data): self.demo_window.update_frame(d))
            except Exception:
                time.sleep(0.5)
            finally:
                try:
                    s.close()
                except Exception:
                    pass

    def fetch_blocklist(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((ADMIN_IP, LOG_PORT))
            client.send("ACTION: GET_BLOCKLIST".encode())
            response = client.recv(4096).decode()
            client.close()
            self.blocklist_cache = json.loads(response)
        except Exception as e:
            print(f"[ERROR fetch_blocklist]: {e}")
            self.blocklist_cache = []
    def show_restricted_warning(self, window_text, category):
        warn = ctk.CTkToplevel(self)
        warn.title("WARNING")
        center_window(warn, 450, 220)
        warn.attributes("-topmost", True)
        warn.configure(fg_color="#8b0000")
        ctk.CTkLabel(warn, text="⚠ RESTRICTED SITE DETECTED", font=("Arial", 18, "bold"), text_color="white").pack(pady=15)
        ctk.CTkLabel(warn, text=f"Category: {category.upper()}", font=("Arial", 13, "bold"), text_color="yellow").pack()
        ctk.CTkLabel(warn, text=window_text, font=("Arial", 11), text_color="white", wraplength=400).pack(pady=10)
        ctk.CTkLabel(warn, text="This activity has been reported to your teacher.", text_color="white").pack(pady=5)
        ctk.CTkButton(warn, text="OK", fg_color="white", text_color="#8b0000", command=warn.destroy).pack(pady=10)

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", LISTENER_PORT))
        server.listen(5)
        while True:
            try:
                conn, addr = server.accept()
                command = conn.recv(1024).decode().strip()
                
                session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_session.json")
                is_logged_in = os.path.exists(session_path)
                
                if not is_logged_in and command in ["LOCK", "UNLOCK", "SHUTDOWN", "REBOOT", "SLEEP", "START_DEMO", "STOP_DEMO"]:
                    conn.close()
                    continue

                if command == "LOCK": 
                    self.after(0, self.show_lock)
                elif command == "UNLOCK":
                    self.after(0, self.hide_lock)
                elif command == "START_DEMO":
                    self.in_demo_mode = True
                    self.after(0, self.open_demo_viewer)
                elif command == "STOP_DEMO":
                    self.in_demo_mode = False
                    self.after(0, self.close_demo_viewer)
                elif command.startswith("MSG:"):
                    msg_content = command.replace("MSG:", "", 1)
                    self.after(0, lambda: self.show_teacher_message(msg_content))
                elif command.startswith("URL:"):
                    url_content = command.replace("URL:", "", 1)
                    self.after(0, lambda: self.open_student_browser(url_content))
                elif command == "SHUTDOWN":
                    os.system("shutdown /s /t 1")
                elif command == "REBOOT":
                    os.system("shutdown /r /t 1")
                elif command == "SLEEP":
                    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                conn.close()
            except: break

    def open_demo_viewer(self):
        if not self.demo_window or not self.demo_window.winfo_exists():
            self.demo_window = DemoViewer(self)

    def close_demo_viewer(self):
        if self.demo_window and self.demo_window.winfo_exists():
            self.demo_window.close_demo()
            self.demo_window = None

    def show_lock(self):
        if not self.active_lock:
            self.active_lock = LockScreen(self)

    def hide_lock(self):
        if self.active_lock:
            self.active_lock.destroy()
            self.active_lock = None

    def show_teacher_message(self, message):
        msg_win = ctk.CTkToplevel(self)
        msg_win.title("Mensahe mula sa Guro")
        center_window(msg_win, 400, 200)
        msg_win.attributes("-topmost", True)
        msg_win.grab_set()
        
        ctk.CTkLabel(msg_win, text="ANUNSYO MULA SA GURO", font=("Arial", 14, "bold"), text_color="#1f6aa5").pack(pady=15)
        
        txt_box = ctk.CTkTextbox(msg_win, width=350, height=80)
        txt_box.insert("1.0", message)
        txt_box.configure(state="disabled")
        txt_box.pack(pady=5)
        
        ctk.CTkButton(msg_win, text="OK", command=msg_win.destroy).pack(pady=15)

    def open_student_browser(self, url):
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        webbrowser.open_new_tab(url)

    def fetch_teachers_and_labs(self):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((ADMIN_IP, LOG_PORT))
            client.send("ACTION: GET_TEACHERS".encode())
            response = client.recv(4096).decode()
            client.close()
            teachers = json.loads(response)
            if teachers:
                self.teacher_map = {f"{t['full_name']} ({t['username']})": t["id"] for t in teachers}
                self.teacher_dropdown.configure(values=list(self.teacher_map.keys()))
                self.teacher_dropdown.set(list(self.teacher_map.keys())[0])
            else:
                self.teacher_dropdown.configure(values=["No teachers found"])
        except Exception as e:
            self.teacher_dropdown.configure(values=["Connection failed"])
            print(f"[ERROR fetch_teachers]: {e}")

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(3)
            client.connect((ADMIN_IP, LOG_PORT))
            client.send("ACTION: GET_LABS".encode())
            response = client.recv(4096).decode()
            client.close()
            labs = json.loads(response)
            if labs:
                self.lab_map = {lab["name"]: lab["id"] for lab in labs}
                self.lab_dropdown.configure(values=list(self.lab_map.keys()))
                self.lab_dropdown.set(list(self.lab_map.keys())[0])
            else:
                self.lab_dropdown.configure(values=["No labs found"])
        except Exception as e:
            self.lab_dropdown.configure(values=["Connection failed"])
            print(f"[ERROR fetch_labs]: {e}")

    def check_login(self):
        user = self.user_entry.get().strip()
        pwd = self.pass_entry.get().strip()

        if not user or not pwd:
            self.error_label.configure(text="Punan ang lahat ng kahon.", text_color="orange")
            return

        selected_teacher_name = self.teacher_dropdown.get()
        selected_lab_name = self.lab_dropdown.get()
        teacher_id = self.teacher_map.get(selected_teacher_name)
        lab_id = self.lab_map.get(selected_lab_name)

        if not teacher_id or not lab_id:
            self.error_label.configure(text="Pumili ng teacher at lab.", text_color="orange")
            return

        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ADMIN_IP, LOG_PORT))

            msg = f"ACTION: LOGIN_CHECK | USER: {user} | PWD: {pwd} | TEACHERID: {teacher_id} | LABID: {lab_id}"
            client.send(msg.encode())

            response = client.recv(1024).decode().strip()
            client.close()

            if response == "SUCCESS":
                session_data = {"username": user}
                session_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_session.json")
                with open(session_path, "w") as f:
                    json.dump(session_data, f)

                self.notify_teacher("LOGIN", user)

                threading.Thread(target=screen_sender.start_stream, args=(TEACHER_IP,), daemon=True).start()
                threading.Thread(target=screen_sender.start_admin_stream, daemon=True).start()
                threading.Thread(target=screen_sender.start_live_monitoring, args=(TEACHER_IP,), daemon=True).start()
                threading.Thread(target=screen_sender.start_live_monitoring, args=(ADMIN_IP,), daemon=True).start()

                self.withdraw()
                self.webcam_overlay = StudentWebcamOverlay(self, username=user, teacher_ip=TEACHER_IP, log_port=LOG_PORT)
                StudentDashboard(username=user, master_app=self)

            elif response == "TEACHER_OFFLINE":
                self.error_label.configure(text="Wala pang online na teacher. Maghintay.", text_color="red")
            elif response == "LAB_MISMATCH":
                self.error_label.configure(text="Mali ang piniling teacher/lab.", text_color="red")
            else:
                self.error_label.configure(text="Invalid credentials o hindi pa na-approve!", text_color="red")
        except Exception as e:
            self.error_label.configure(text=f"Hindi makakonekta sa Guro: {e}", text_color="red")
        
    def notify_teacher(self, action, username):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ADMIN_IP, LOG_PORT))
            msg = f"ACTION: {action} | USER: {username}"
            client.send(msg.encode())
            client.close()
        except Exception:
            pass

if __name__ == "__main__":
    app = LoginApp()
    app.mainloop()