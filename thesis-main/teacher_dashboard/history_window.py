import customtkinter as ctk
import tkinter.ttk as ttk
import socket
import json
from network_config import ADMIN_IP, LOG_PORT
from ui_utils import center_window


def _fetch_history_from_admin():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((ADMIN_IP, LOG_PORT))
        s.sendall("ACTION: GET_ALL_HISTORY".encode())
        response = s.recv(65536).decode()
        s.close()
        return json.loads(response) if response else []
    except Exception as e:
        print(f"[ERROR fetching history from admin]: {e}")
        return []


def open_history_window(master, login_history_data=None):
    """login_history_data param kept for compatibility with the existing
    call site, but is no longer used — real history now comes from Admin's
    database over the network, same as Admin's own Logs & History tab."""
    history_win = ctk.CTkToplevel(master)
    history_win.title("Student Login & Logout History")
    center_window(history_win, 750, 450)

    lbl_title = ctk.CTkLabel(history_win, text="Lab User Session History", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_title.pack(pady=10)

    table_frame = ctk.CTkFrame(history_win)
    table_frame.pack(fill="both", expand=True, padx=20, pady=10)

    columns = ("Name", "Role", "Lab", "Login Time", "Logout Time", "Duration")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=110, anchor="center")

    tree.pack(side="left", fill="both", expand=True)

    def load_data():
        for row in tree.get_children():
            tree.delete(row)

        history = _fetch_history_from_admin()
        for item in history:
            display_name = item.get("full_name") or item.get("username")
            duration = item.get("duration_secs") or 0
            mins, secs = divmod(duration, 60)
            hrs, mins = divmod(mins, 60)
            duration_str = f"{hrs}h {mins}m {secs}s" if item.get("logout_time") else "Active"

            tree.insert("", "end", values=(
                display_name,
                item.get("role", ""),
                item.get("lab_name") or "N/A",
                item.get("login_time", ""),
                item.get("logout_time") or "Still active",
                duration_str,
            ))

    ctk.CTkButton(history_win, text="Refresh", fg_color="#1f6aa5", command=load_data).pack(pady=10)

    load_data()