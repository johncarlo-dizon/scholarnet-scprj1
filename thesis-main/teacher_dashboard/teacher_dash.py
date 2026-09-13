import customtkinter as ctk
import tkinter as tk
import socket
import threading
import time
import struct
import mss
import numpy as np
import cv2
import pyautogui
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from .network_utils import send_command
from .screen_receiver import ScreenViewer
from network_config import BROADCAST_PORT
from ui_utils import center_window
from .history_window import open_history_window
from .student_cards import setup_grid_layout, create_student_card

from .account_approvals import open_account_approvals
from .inbox_window import open_inbox_window  
from database import db

class TeacherDashboard(ctk.CTkToplevel):
    def __init__(self, master_app):
        super().__init__()
        self.inbox_logs_data = []
        self.current_inbox_win = None 
        self.master_app = master_app
        self.connected_students = {}
        self.student_cards = {}
        self.login_history_data = []
        self.active_viewers = {}  
        self.is_broadcasting_demo = False  
        self.btn_fullscreen_demo = None  
        self.student_histories = {} 
        
        from ui_utils import center_window
        self.title("Teacher Dashboard")
        center_window(self, 1200, 800)
        
        # --- TOP TOOLBAR ---
        self.top_toolbar = ctk.CTkFrame(self, height=65, corner_radius=0)
        self.top_toolbar.pack(side="top", fill="x")
        
        toolbar_items = [
            ("Monitoring", None),
            ("Lock", self.lock_all_students),
            ("Unlock", self.unlock_all_students),
            ("Logout user", None),
            ("Text message", self.open_text_message_dialog),
            ("Run program", None),
            ("Open website", self.open_website_dialog),
            ("Inbox", lambda: open_inbox_window(self)), 
            ("Screenshot", None),
            ("History", lambda: open_history_window(self, self.master_app.login_history_data)),
            ("Approvals", lambda: open_account_approvals(self)),
            ("Reset Password", self.open_reset_password_dialog),
            ("Refresh", self.refresh_connections),
        ]
        
        for btn_text, btn_command in toolbar_items:
            is_accent = btn_text in ("Refresh", "Inbox")

            btn_kwargs = dict(
                text=btn_text,
                image=None,
                compound="top",
                width=75,
                height=50,
                font=ctk.CTkFont(size=10),
                command=btn_command if btn_command else lambda t=btn_text: print(f"{t} clicked")
            )
            if is_accent:
                btn_kwargs["fg_color"] = "#1f6aa5"
                btn_kwargs["hover_color"] = "#144870"
            # else: no fg_color override — button uses the theme's default styling

            btn = ctk.CTkButton(self.top_toolbar, **btn_kwargs)
            btn.pack(side="left", padx=1, pady=5)
            

        # --- TEST BUTTON PARA SA INBOX ---
        test_inbox_btn = ctk.CTkButton(
            self.top_toolbar, 
            text="Test Inbox Log", 
            fg_color="#b58900", 
            hover_color="#856300",
            width=75,
            height=50,
            font=ctk.CTkFont(size=10),
            command=self.add_test_log
        )
        test_inbox_btn.pack(side="left", padx=1, pady=5)

        # --- MAIN GRID PARA SA MGA PC NG ESTUDYANTE ---
        setup_grid_layout(self)

        from .network_listeners import hydrate_dashboard
        hydrate_dashboard(self.master_app, self)

        # --- BOTTOM STATUS BAR ---
        self.bottom_bar = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.bottom_bar.pack(side="bottom", fill="x")
        
        self.lbl_rooms = ctk.CTkButton(self.bottom_bar, text="Computer rooms", fg_color="transparent", text_color=("black", "white"), width=100)
        self.lbl_rooms.pack(side="left", padx=10)

        self.lbl_screenshots = ctk.CTkButton(self.bottom_bar, text="Screenshots", fg_color="transparent", text_color=("black", "white"), width=90)
        self.lbl_screenshots.pack(side="left", padx=5)
        
        self.search_entry = ctk.CTkEntry(self.bottom_bar, placeholder_text="Search users and computers", width=220)
        self.search_entry.pack(side="left", padx=15, pady=5)

    def add_test_log(self):
        """Pansamantalang function para magdagdag ng dummy log at i-test ang Inbox UI"""
        import datetime
        new_log = {
            "time": datetime.datetime.now().strftime('%H:%M:%S'),
            "message": "[192.168.1.50] Test Expression: Hello Teacher!"
        }
        self.inbox_logs_data.append(new_log)
        print(f"[DEBUG] Bagong log idinagdag: {new_log}")
        self.refresh_inbox_ui()

    def open_reset_password_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Reset Student Password")
        center_window(dialog, 350, 220)
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(dialog, text="Reset Student Password", font=("Arial", 14, "bold")).pack(pady=15)
        username_entry = ctk.CTkEntry(dialog, placeholder_text="Student Username", width=250)
        username_entry.pack(pady=10)

        status_lbl = ctk.CTkLabel(dialog, text="")
        status_lbl.pack(pady=5)

        def do_reset():
            username = username_entry.get().strip()
            user = db.get_user_by_username(username)
            if not user or user["role"] != "student":
                status_lbl.configure(text="Student not found!", text_color="red")
                return
            db.reset_to_default_password(user["id"])
            status_lbl.configure(
                text=f"Reset! New password: {db.DEFAULT_RESET_PASSWORD}",
                text_color="green"
            )

        ctk.CTkButton(dialog, text=f"Reset to '{db.DEFAULT_RESET_PASSWORD}'",
                    fg_color="red", command=do_reset).pack(pady=15)

    def refresh_inbox_ui(self):
        """Kusa nitong nire-refresh ang Inbox window kapag may bagong pumasok na data"""
        if self.current_inbox_win and self.current_inbox_win.winfo_exists():
            try:
                self.current_inbox_win.destroy()
            except:
                pass
            open_inbox_window(self)

    def update_history_ui(self, ip):
        pass

    def show_notification(self, message):
        pass

    def start_teacher_broadcast(self):
        def broadcast_server_loop():
            pass  
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            
            try:
                server_sock.bind(('0.0.0.0', BROADCAST_PORT))
                server_sock.listen(15)
                server_sock.settimeout(0.5)
            except Exception as e:
                print(f"Broadcast bind error: {e}")
                return

            clients = []
            
            def accept_clients():
                while self.is_broadcasting_demo:
                    try:
                        conn, addr = server_sock.accept()
                        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        conn.setblocking(False)
                        clients.append(conn)
                    except socket.timeout:
                        continue
                    except:
                        break

            accept_thread = threading.Thread(target=accept_clients, daemon=True)
            accept_thread.start()

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                
                while self.is_broadcasting_demo:
                    loop_start = time.time()
                    try:
                        img = sct.grab(monitor)
                        frame = np.array(img)
                        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        
                        try:
                            mouse_x, mouse_y = pyautogui.position()
                            cv2.circle(frame_bgr, (mouse_x, mouse_y), 14, (0, 0, 255), -1)
                            cv2.circle(frame_bgr, (mouse_x, mouse_y), 16, (255, 255, 255), 2)
                        except:
                            pass
                        
                        frame_resized = cv2.resize(frame_bgr, (1280, 720), interpolation=cv2.INTER_AREA)
                        _, img_encoded = cv2.imencode('.jpg', frame_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                        img_data = img_encoded.tobytes()
                        header = struct.pack("!I", len(img_data))
                        payload = header + img_data
                        
                        dead_clients = []
                        for client in clients:
                            try:
                                client.sendall(payload)
                            except:
                                dead_clients.append(client)
                        
                        for dead in dead_clients:
                            if dead in clients:
                                clients.remove(dead)
                            try:
                                dead.close()
                            except:
                                pass
                                
                    except Exception as e:
                        print(f"Broadcast loop error: {e}")
                    
                    elapsed = time.time() - loop_start
                    if elapsed < 0.03:
                        time.sleep(0.03 - elapsed)
            
            try:
                server_sock.close()
            except:
                pass
                
            for client in clients:
                try:
                    client.close()
                except:
                    pass

        if not self.is_broadcasting_demo:
            self.is_broadcasting_demo = True
            if self.btn_fullscreen_demo:
                self.btn_fullscreen_demo.configure(text="STOP", fg_color="#a83232", hover_color="#c94444")
            
            for ip in self.student_cards.keys():
                send_command(ip, "START_DEMO")
            
            time.sleep(0.2)
            threading.Thread(target=broadcast_server_loop, daemon=True).start()
            print("[DEBUG] Nagsimula na ang na-optimize na Broadcast Server.")
        else:
            self.is_broadcasting_demo = False
            if self.btn_fullscreen_demo:
                self.btn_fullscreen_demo.configure(text="Fullscreen demo", fg_color="#383838", hover_color="#505050")
            
            for ip in self.student_cards.keys():
                send_command(ip, "STOP_DEMO")

    def start_teacher_broadcaster(self):
        pass

    def refresh_connections(self):
        print("[DEBUG] Nirerefresh ang student cards sa dashboard...")
        for ip, card_info in list(self.student_cards.items()):
            try:
                if isinstance(card_info, dict) and "frame" in card_info:
                    card_info["frame"].destroy()
                elif hasattr(card_info, "destroy"):
                    card_info.destroy()
            except Exception as e:
                print(f"Error sa pagbura ng card para sa {ip}: {e}")
                
        self.student_cards.clear()
        self.connected_students.clear()
        print("[DEBUG] Refresh tapos na.")

    def setup_grid_layout(self):
        setup_grid_layout(self)

    def show_context_menu(self, event, ip, name, role="student"):
        context_menu = tk.Menu(self, tearoff=0, bg="#f0f0f0", fg="black", font=("Arial", 10))
        context_menu.add_command(label="Remote View", command=lambda: self.open_full_view(ip, is_control=False))
        context_menu.add_separator()
        context_menu.add_command(label="Lock", command=lambda: send_command(ip, "LOCK"))
        context_menu.add_command(label="Unlock", command=lambda: send_command(ip, "UNLOCK"))
        context_menu.add_separator()
        context_menu.add_command(label="Message", command=lambda: self.open_single_text_message_dialog(ip))
        context_menu.add_separator()
        context_menu.add_command(label="Open website", command=lambda: self.open_single_website_dialog(ip))
        context_menu.add_separator()
        context_menu.add_command(label="Remote Control", command=lambda: self.open_full_view(ip, is_control=True))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def open_text_message_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Send Text Message to Students")
        center_window(dialog, 400, 250)
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text="I-type ang mensahe para sa lahat ng estudyante:", font=("Arial", 12, "bold")).pack(pady=15)
        msg_entry = ctk.CTkTextbox(dialog, width=350, height=100)
        msg_entry.pack(pady=5)
        
        def send_msg():
            message = msg_entry.get("1.0", "end-1c").strip()
            if message:
                for ip in self.student_cards.keys():
                    send_command(ip, f"MSG:{message}")
                dialog.destroy()
                
        ctk.CTkButton(dialog, text="Broadcast Message", fg_color="green", command=send_msg).pack(pady=15)

    def open_single_text_message_dialog(self, ip):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Send Message to {ip}")
        center_window(dialog, 400, 250)
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text=f"I-type ang mensahe para sa PC ({ip}):", font=("Arial", 12, "bold")).pack(pady=15)
        msg_entry = ctk.CTkTextbox(dialog, width=350, height=100)
        msg_entry.pack(pady=5)
        
        def send_single_msg():
            message = msg_entry.get("1.0", "end-1c").strip()
            if message:
                send_command(ip, f"MSG:{message}")
                dialog.destroy()
                
        ctk.CTkButton(dialog, text="Send Message", fg_color="green", command=send_single_msg).pack(pady=15)

    def open_website_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Open Website on All Students")
        center_window(dialog, 400, 200)
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text="I-type ang URL (hal. https://www.facebook.com):", font=("Arial", 12, "bold")).pack(pady=15)
        url_entry = ctk.CTkEntry(dialog, width=350, placeholder_text="https://...")
        url_entry.pack(pady=5)
        
        def send_url():
            url = url_entry.get().strip()
            if url:
                for ip in self.student_cards.keys():
                    send_command(ip, f"URL:{url}")
                dialog.destroy()
                
        ctk.CTkButton(dialog, text="Open Website", fg_color="green", command=send_url).pack(pady=15)

    def open_single_website_dialog(self, ip):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Open Website on {ip}")
        center_window(dialog, 400, 200)
        dialog.attributes("-topmost", True)
        ctk.CTkLabel(dialog, text=f"I-type ang URL para sa PC ({ip}):", font=("Arial", 12, "bold")).pack(pady=15)
        url_entry = ctk.CTkEntry(dialog, width=350, placeholder_text="https://...")
        url_entry.pack(pady=5)
        
        def send_single_url():
            url = url_entry.get().strip()
            if url:
                send_command(ip, f"URL:{url}")
                dialog.destroy()
                
        ctk.CTkButton(dialog, text="Open Website", fg_color="green", command=send_single_url).pack(pady=15)

    def open_full_view(self, student_ip, is_control=False):
        try:
            if student_ip in self.active_viewers:
                try:
                    self.active_viewers[student_ip].destroy()
                except:
                    pass
            
            viewer = ScreenViewer(student_ip, control_mode=is_control)
            self.active_viewers[student_ip] = viewer
            
            def on_viewer_close():
                if student_ip in self.active_viewers:
                    del self.active_viewers[student_ip]
                viewer.destroy()
                
            viewer.protocol("WM_DELETE_WINDOW", on_viewer_close)
        except Exception as e:
            print(f"Error sa pagbubukas ng ScreenViewer: {e}")


    def lock_all_students(self):
        for ip in self.student_cards.keys():
            send_command(ip, "LOCK")

    def unlock_all_students(self):
        for ip in self.student_cards.keys():
            send_command(ip, "UNLOCK")

    def reboot_all_students(self):
        for ip in self.student_cards.keys():
            send_command(ip, "REBOOT")

    def shutdown_all_students(self):
        for ip in self.student_cards.keys():
            send_command(ip, "SHUTDOWN")

    def sleep_all_students(self):
        for ip in self.student_cards.keys():
            send_command(ip, "SLEEP")