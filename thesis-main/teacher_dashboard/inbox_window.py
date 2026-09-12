import customtkinter as ctk
from database import db

def open_inbox_window(master_dashboard):
    if hasattr(master_dashboard, 'current_inbox_win') and master_dashboard.current_inbox_win:
        try:
            master_dashboard.current_inbox_win.destroy()
        except:
            pass

    inbox_win = ctk.CTkToplevel(master_dashboard)
    master_dashboard.current_inbox_win = inbox_win

    inbox_win.title("Teacher's Student Activity Inbox")
    inbox_win.geometry("600x450")

    ctk.CTkLabel(inbox_win, text="Real-time Student Activity Inbox", font=("Arial", 16, "bold")).pack(pady=10)

    frame = ctk.CTkScrollableFrame(inbox_win, width=550, height=320)
    frame.pack(pady=10, padx=10, fill="both", expand=True)

    teacher_id = getattr(master_dashboard.master_app, 'current_teacher_user_id', None)
    alerts = db.get_alerts_for_teacher(teacher_id) if teacher_id else []

    if alerts:
        ctk.CTkLabel(frame, text="⚠ RESTRICTED SITE ALERTS", font=("Arial", 13, "bold"), text_color="red").pack(anchor="w", pady=(5, 5))
        for a in alerts:
            display_name = a["full_name"] or a["username"]
            text = f"[{a['timestamp']}] {display_name}: {a['matched_text']} ({a['category']})"
            lbl = ctk.CTkLabel(frame, text=text, anchor="w", justify="left", font=("Arial", 12, "bold"),
                                text_color="white", fg_color="#8b0000", corner_radius=6, wraplength=520)
            lbl.pack(fill="x", padx=5, pady=3, ipady=6)

    if not hasattr(master_dashboard, 'inbox_logs_data') or not master_dashboard.inbox_logs_data:
        ctk.CTkLabel(frame, text="Wala pang natatanggap na aktibidad mula sa mga estudyante.", text_color="gray").pack(pady=20)
    else:
        for log in reversed(master_dashboard.inbox_logs_data):
            log_text = f"[{log.get('time', '')}] {log.get('message', '')}"
            lbl = ctk.CTkLabel(frame, text=log_text, anchor="w", justify="left", font=("Arial", 12))
            lbl.pack(fill="x", padx=5, pady=2)

    def clear_inbox():
        if hasattr(master_dashboard, 'inbox_logs_data'):
            master_dashboard.inbox_logs_data.clear()
        master_dashboard.current_inbox_win = None
        inbox_win.destroy()
        open_inbox_window(master_dashboard)

    def acknowledge_alerts():
        for a in alerts:
            db.acknowledge_alert(a["id"])
        master_dashboard.current_inbox_win = None
        inbox_win.destroy()
        open_inbox_window(master_dashboard)

    def on_close():
        master_dashboard.current_inbox_win = None
        inbox_win.destroy()

    inbox_win.protocol("WM_DELETE_WINDOW", on_close)

    btn_row = ctk.CTkFrame(inbox_win, fg_color="transparent")
    btn_row.pack(pady=10)
    ctk.CTkButton(btn_row, text="Clear Activity", fg_color="#d9534f", hover_color="#c9302c", command=clear_inbox).pack(side="left", padx=5)
    if alerts:
        ctk.CTkButton(btn_row, text="Acknowledge Alerts", fg_color="#1f6aa5", command=acknowledge_alerts).pack(side="left", padx=5)