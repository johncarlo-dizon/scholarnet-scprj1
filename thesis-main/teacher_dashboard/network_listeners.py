import socket
import threading
import io
from datetime import datetime
from PIL import Image, ImageTk

from network_config import TEACHER_IP


# NOTE: the old start_log_listener() that lived in this file has been removed.
# login.py's own LoginApp.start_log_listener already owns port 5001 and handles
# LOGIN_CHECK, REGISTER, GET_TEACHERS, CHANGE_PWD, GET_HISTORY, LOGIN, LOGOUT,
# EXPRESSION, and ACTIVITY. Having a second listener here trying to bind the
# same port was silently failing every time and doing nothing.


def handle_student_expression(self, expression_text, sender_ip):
    """self here is always the LoginApp instance (see login.py's dispatch)."""
    try:
        parts = expression_text.split("|")
        expression = parts[1].strip() if len(parts) >= 2 else expression_text.strip()

        dashboard = getattr(self, "active_teacher_dashboard", None)
        if dashboard and sender_ip in dashboard.student_cards:
            target_card_info = dashboard.student_cards[sender_ip]
            target_card_info["expression"] = expression
            current_name = target_card_info["name"].split(" | [")[0].strip()
            target_card_info["name"] = f"{current_name} | [{expression}]"

            if "info_label" in target_card_info and target_card_info["info_label"].winfo_exists():
                target_card_info["info_label"].configure(text=f"{target_card_info['name']} ({sender_ip})")

        # Always remember the latest expression at the persistent level too,
        # so a freshly (re)opened dashboard can show it immediately.
        if not hasattr(self, "student_expressions"):
            self.student_expressions = {}
        self.student_expressions[sender_ip] = expression
    except Exception as e:
        print(f"[ERROR parsing expression]: {e}")


def update_student_card_name(self, username, ip):
    """self here is always the LoginApp instance. Updates the persistent name
    record, and — if a dashboard is currently open — creates/updates its
    visible card, but only if this student's lab matches the teacher's
    currently selected lab."""
    from database import db

    pc_label = f"PC {ip.split('.')[-1]}"
    display_name = f"{username} - {pc_label}"

    if not hasattr(self, "student_display_names"):
        self.student_display_names = {}
    self.student_display_names[ip] = display_name

    if not hasattr(self, "ip_to_username"):
        self.ip_to_username = {}
    self.ip_to_username[ip] = username

    dashboard = getattr(self, "active_teacher_dashboard", None)
    if dashboard is None:
        return

    teacher_lab_id = getattr(self, "current_teacher_lab_id", None)
    student_user = db.get_user_by_username(username)
    student_lab_id = student_user["lab_id"] if student_user else None

    if teacher_lab_id is not None and student_lab_id != teacher_lab_id:
        # Student is in a different lab than this teacher — remove any stale card
        if ip in dashboard.student_cards:
            try:
                card_info = dashboard.student_cards[ip]
                if "frame" in card_info and card_info["frame"].winfo_exists():
                    card_info["frame"].destroy()
            except Exception:
                pass
            del dashboard.student_cards[ip]
        return

    if ip not in dashboard.student_cards or "frame" not in dashboard.student_cards[ip] \
            or not dashboard.student_cards[ip]["frame"].winfo_exists():
        from .student_cards import create_student_card
        create_student_card(dashboard, display_name, ip, len(dashboard.student_cards))
    else:
        card_info = dashboard.student_cards[ip]
        card_info["name"] = display_name
        if "info_label" in card_info and card_info["info_label"].winfo_exists():
            card_info["info_label"].configure(text=f"{display_name} ({ip})")


def hydrate_dashboard(self, dashboard):
    """Called once when a TeacherDashboard opens, to immediately rebuild
    cards + last-known frames for students already connected — filtered to
    only this teacher's currently selected lab."""
    from database import db

    names = getattr(self, "student_display_names", {})
    frames = getattr(self, "latest_frames", {})
    expressions = getattr(self, "student_expressions", {})
    ip_to_username = getattr(self, "ip_to_username", {})
    teacher_lab_id = getattr(self, "current_teacher_lab_id", None)

    for ip in getattr(self, "connected_students", {}).keys():
        username = ip_to_username.get(ip)
        if username and teacher_lab_id is not None:
            student_user = db.get_user_by_username(username)
            student_lab_id = student_user["lab_id"] if student_user else None
            if student_lab_id != teacher_lab_id:
                continue

        display_name = names.get(ip, f"User - {ip}")
        if ip in expressions:
            display_name = f"{display_name} | [{expressions[ip]}]"

        from .student_cards import create_student_card
        create_student_card(dashboard, display_name, ip, len(dashboard.student_cards))

        if ip in frames:
            update_thumbnail_frame_for(dashboard, ip, frames[ip])


def update_thumbnail_frame_for(dashboard, ip, img_tk):
    if ip in dashboard.student_cards:
        lbl = dashboard.student_cards[ip]["preview"]
        lbl.configure(image=img_tk, text="")
        lbl.image = img_tk


def update_thumbnail_frame(self, ip, img_tk):
    """self here is always the LoginApp instance. Always remembers the latest
    frame persistently, and pushes it into the live dashboard if one is open."""
    if not hasattr(self, "latest_frames"):
        self.latest_frames = {}
    self.latest_frames[ip] = img_tk

    dashboard = getattr(self, "active_teacher_dashboard", None)
    if dashboard is not None:
        update_thumbnail_frame_for(dashboard, ip, img_tk)


def record_login(self, name, ip):
    """self here is always the LoginApp instance — login_history_data now
    lives there so it survives dashboard close/reopen."""
    login_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in self.login_history_data:
        if item["ip"] == ip and item["logout"] == "Active / Online":
            return
    self.login_history_data.append({
        "name": name, "ip": ip, "login": login_time, "logout": "Active / Online", "duration": "-"
    })


def record_logout(self, ip):
    logout_time = datetime.now()
    logout_str = logout_time.strftime("%Y-%m-%d %H:%M:%S")
    for item in self.login_history_data:
        if item["ip"] == ip and item["logout"] == "Active / Online":
            item["logout"] = logout_str
            login_dt = datetime.strptime(item["login"], "%Y-%m-%d %H:%M:%S")
            duration_sec = int((logout_time - login_dt).total_seconds())
            hours, remainder = divmod(duration_sec, 3600)
            minutes, seconds = divmod(remainder, 60)
            item["duration"] = f"{hours}h {minutes}m {seconds}s"
            break


def start_persistent_stream_listeners(self):
    """Call this exactly ONCE, from LoginApp.__init__. self is the LoginApp
    instance and lives for the whole program, so these listeners never get
    torn down and re-bound when a TeacherDashboard window opens/closes."""

    if not hasattr(self, "connected_students"):
        self.connected_students = {}
    if not hasattr(self, "student_display_names"):
        self.student_display_names = {}
    if not hasattr(self, "latest_frames"):
        self.latest_frames = {}
    if not hasattr(self, "student_expressions"):
        self.student_expressions = {}
    if not hasattr(self, "login_history_data"):
        self.login_history_data = []
    if not hasattr(self, "active_teacher_dashboard"):
        self.active_teacher_dashboard = None

    # --- Main Stream Listener (Port 9998) ---
    def handle_client(conn, addr):
        student_ip = addr[0]
        self.connected_students[student_ip] = conn
        display_name = f"User - {student_ip}"

        try:
            conn.settimeout(3.0)
            raw_user_info = conn.recv(128).decode('utf-8', errors='ignore').strip()
            conn.settimeout(None)

            if "NAME:" in raw_user_info:
                parts = raw_user_info.split("NAME:")
                if len(parts) > 1:
                    actual_username = parts[1].split("\n")[0].strip()
                    if actual_username:
                        display_name = f"{actual_username} - PC {student_ip.split('.')[-1]}"
        except Exception:
            conn.settimeout(None)

        clean_username = display_name.split(" - ")[0]
        if hasattr(self, 'after'):
            self.after(0, lambda u=clean_username, ip=student_ip: update_student_card_name(self, u, ip))
            self.after(0, lambda: record_login(self, display_name, student_ip))

        try:
            while True:
                raw_length = conn.recv(4)
                if not raw_length:
                    break
                frame_length = int.from_bytes(raw_length, byteorder='big')

                frame_data = b""
                while len(frame_data) < frame_length:
                    packet = conn.recv(frame_length - len(frame_data))
                    if not packet:
                        break
                    frame_data += packet

                if len(frame_data) == frame_length:
                    image = Image.open(io.BytesIO(frame_data)).resize((240, 150), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(image)
                    if hasattr(self, 'after'):
                        self.after(0, lambda ip=student_ip, img=img_tk: update_thumbnail_frame(self, ip, img))
        except Exception as e:
            print(f"Stream error with {student_ip}: {e}")
        finally:
            conn.close()
            if student_ip in self.connected_students:
                del self.connected_students[student_ip]

            def remove_card_ui():
                dashboard = getattr(self, "active_teacher_dashboard", None)
                if dashboard and student_ip in dashboard.student_cards:
                    try:
                        card_info = dashboard.student_cards[student_ip]
                        if isinstance(card_info, dict) and "frame" in card_info and card_info["frame"].winfo_exists():
                            card_info["frame"].destroy()
                    except Exception:
                        pass
                    del dashboard.student_cards[student_ip]

            if hasattr(self, 'after'):
                self.after(0, remove_card_ui)
                self.after(0, lambda: record_logout(self, student_ip))

    def stream_listener():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((TEACHER_IP, 9998))
            server.listen(10)
        except Exception as e:
            print(f"[ERROR] Stream listener could not bind {TEACHER_IP}:9998: {e}")
            return
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Stream listener accept failed: {e}")

    threading.Thread(target=stream_listener, daemon=True).start()

    # --- Remote View Listener (Port 9997) ---
    def handle_remote_client(conn, addr):
        student_ip = addr[0]
        try:
            while True:
                raw_length = conn.recv(4)
                if not raw_length:
                    break
                frame_length = int.from_bytes(raw_length, byteorder='big')

                frame_data = b""
                while len(frame_data) < frame_length:
                    packet = conn.recv(frame_length - len(frame_data))
                    if not packet:
                        break
                    frame_data += packet

                if len(frame_data) == frame_length:
                    image = Image.open(io.BytesIO(frame_data))
                    img_tk = ImageTk.PhotoImage(image)

                    dashboard = getattr(self, "active_teacher_dashboard", None)
                    if dashboard and hasattr(dashboard, 'active_viewers') and student_ip in dashboard.active_viewers:
                        viewer = dashboard.active_viewers[student_ip]
                        if viewer.winfo_exists():
                            viewer.after(0, lambda img=img_tk, v=viewer: v.update_image(img))
        except Exception as e:
            print(f"Remote view error for {student_ip}: {e}")
        finally:
            conn.close()

    def remote_listener():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((TEACHER_IP, 9997))
            server.listen(10)
        except Exception as e:
            print(f"[ERROR] Remote view listener could not bind {TEACHER_IP}:9997: {e}")
            return
        while True:
            try:
                conn, addr = server.accept()
                threading.Thread(target=handle_remote_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Remote listener accept failed: {e}")

    threading.Thread(target=remote_listener, daemon=True).start()