import customtkinter as ctk
from database import db
from ui_utils import center_window
def open_account_approvals(master_teacher):
    window = ctk.CTkToplevel(master_teacher)
    window.title("Account Approvals Management")
    center_window(window, 750, 550)
    window.attributes("-topmost", True)

    ctk.CTkLabel(window, text="Student Account Requests", font=("Arial", 18, "bold")).pack(pady=15)

    tabview = ctk.CTkTabview(window, width=700, height=380)
    tabview.pack(padx=20, pady=5)

    tab_pending = tabview.add("Pending")
    tab_accepted = tabview.add("Accepted")
    tab_declined = tabview.add("Declined")

    def load_data():
        for widget in tab_pending.winfo_children(): widget.destroy()
        for widget in tab_accepted.winfo_children(): widget.destroy()
        for widget in tab_declined.winfo_children(): widget.destroy()

        pending = db.get_pending_registrations()
        for acc in pending:
            frm = ctk.CTkFrame(tab_pending)
            frm.pack(fill="x", padx=10, pady=5)
            label_text = f"{acc['full_name']} ({acc['username']}) — {acc['course_section']}"
            ctk.CTkLabel(frm, text=label_text, font=("Arial", 12)).pack(side="left", padx=10)

            ctk.CTkButton(frm, text="Decline", fg_color="red", width=80,
                          command=lambda uid=acc["id"]: update_status(uid, "declined")).pack(side="right", padx=5)
            ctk.CTkButton(frm, text="Accept", fg_color="green", width=80,
                          command=lambda uid=acc["id"]: update_status(uid, "approved")).pack(side="right", padx=5)

        with db.get_conn() as conn:
            accepted_rows = conn.execute(
                "SELECT * FROM users WHERE role='student' AND status='approved'"
            ).fetchall()
            declined_rows = conn.execute(
                "SELECT * FROM users WHERE role='student' AND status='declined'"
            ).fetchall()

        for acc in accepted_rows:
            frm = ctk.CTkFrame(tab_accepted)
            frm.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(frm, text=f"{acc['full_name']} ({acc['username']}) (Approved)",
                         text_color="green", font=("Arial", 12)).pack(side="left", padx=10)

        for acc in declined_rows:
            frm = ctk.CTkFrame(tab_declined)
            frm.pack(fill="x", padx=10, pady=5)
            ctk.CTkLabel(frm, text=f"{acc['full_name']} ({acc['username']}) (Rejected)",
                         text_color="red", font=("Arial", 12)).pack(side="left", padx=10)

    def update_status(user_id, new_status):
        if new_status == "approved":
            db.approve_registration(user_id)
        elif new_status == "declined":
            db.decline_registration(user_id)
        load_data()

    ctk.CTkButton(window, text="Refresh List", fg_color="#1f6aa5", command=load_data).pack(pady=10)

    load_data()