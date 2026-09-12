import customtkinter as ctk
import tkinter.ttk as ttk
import socket
from database import db
from teacher_dashboard.network_utils import send_command
from network_config import STUDENT_PC_IP
class AdminDashboard(ctk.CTkToplevel):
    def __init__(self, master_app):
        super().__init__()
        self.master_app = master_app
        self.title("Super Admin Dashboard")
        self.geometry("900x600")

        # --- Top toolbar: all-PC power controls ---
        top_bar = ctk.CTkFrame(self, height=50, fg_color="#333333", corner_radius=0)
        top_bar.pack(side="top", fill="x")

        ctk.CTkButton(top_bar, text="Sleep All", fg_color="#b58900", hover_color="#856300",
                      command=self.sleep_all).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(top_bar, text="Restart All", fg_color="#1f6aa5", hover_color="#144870",
                      command=self.restart_all).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(top_bar, text="Shutdown All", fg_color="#a83232", hover_color="#c94444",
                      command=self.shutdown_all).pack(side="left", padx=5, pady=8)

        tabview = ctk.CTkTabview(self)
        tabview.pack(expand=True, fill="both", padx=20, pady=20)
        
        tabview.add("Logs & History")
        tabview.add("User Management")
        tabview.add("Manage Teachers")
        tabview.add("Lab Monitoring")
        tabview.add("Inventory")
        
        # --- Logs & History Tab ---
        self.search_entry = ctk.CTkEntry(tabview.tab("Logs & History"), placeholder_text="Search student name...")
        self.search_entry.pack(pady=10, fill="x")
        self.search_entry.bind("<KeyRelease>", self.filter_logs)
        
        self.tree = ttk.Treeview(tabview.tab("Logs & History"), columns=("User", "Login", "Logout", "Duration"), show='headings')
        for col in ["User", "Login", "Logout", "Duration"]:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True)
        
        # --- User Management Tab ---
        ctk.CTkLabel(tabview.tab("User Management"), text="Reset Student Password", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.target_user_entry = ctk.CTkEntry(tabview.tab("User Management"), placeholder_text="Enter Student Username")
        self.target_user_entry.pack(pady=10)
        
        ctk.CTkButton(tabview.tab("User Management"), text=f"Reset to '{db.DEFAULT_RESET_PASSWORD}'", 
                    fg_color="red", command=self.reset_student_password).pack(pady=10)
        
        self.status_label = ctk.CTkLabel(tabview.tab("User Management"), text="")
        self.status_label.pack()
        
        self.refresh_table()

        # --- Manage Teachers Tab ---
        teacher_tab = tabview.tab("Manage Teachers")

        ctk.CTkLabel(teacher_tab, text="Create Teacher Account", font=("Arial", 16, "bold")).pack(pady=10)

        self.new_teacher_user = ctk.CTkEntry(teacher_tab, placeholder_text="Username")
        self.new_teacher_user.pack(pady=5)
        self.new_teacher_pass = ctk.CTkEntry(teacher_tab, placeholder_text="Password", show="*")
        self.new_teacher_pass.pack(pady=5)
        self.new_teacher_name = ctk.CTkEntry(teacher_tab, placeholder_text="Full Name")
        self.new_teacher_name.pack(pady=5)

        ctk.CTkButton(teacher_tab, text="Create Teacher", fg_color="green",
                    command=self.create_teacher).pack(pady=10)

        self.teacher_create_status = ctk.CTkLabel(teacher_tab, text="")
        self.teacher_create_status.pack(pady=5)

        ctk.CTkLabel(teacher_tab, text="Existing Teachers", font=("Arial", 14, "bold")).pack(pady=(20, 5))
        self.teacher_list_frame = ctk.CTkScrollableFrame(teacher_tab, width=400, height=180)
        self.teacher_list_frame.pack(pady=5, fill="both", expand=True)
        self.refresh_teacher_list()

        # --- Lab Monitoring Tab ---
        lab_tab = tabview.tab("Lab Monitoring")

        lab_btn_row = ctk.CTkFrame(lab_tab, fg_color="transparent")
        lab_btn_row.pack(pady=15)

        self.lab_buttons = {}
        labs = db.get_all_labs()
        for lab in labs:
            btn = ctk.CTkButton(lab_btn_row, text=lab["name"], width=160,
                                command=lambda lid=lab["id"], lname=lab["name"]: self.show_lab_occupancy(lid, lname))
            btn.pack(side="left", padx=10)
            self.lab_buttons[lab["id"]] = btn

        self.lab_occupancy_label = ctk.CTkLabel(lab_tab, text="Select a lab above to view occupancy.",
                                                font=("Arial", 14, "bold"))
        self.lab_occupancy_label.pack(pady=10)

        self.lab_occupancy_frame = ctk.CTkScrollableFrame(lab_tab, width=500, height=280)
        self.lab_occupancy_frame.pack(pady=5, fill="both", expand=True)

                # --- Inventory Tab ---
        inv_tab = tabview.tab("Inventory")

        # -- Add new item --
        add_item_frame = ctk.CTkFrame(inv_tab, fg_color="transparent")
        add_item_frame.pack(pady=10, fill="x", padx=10)

        ctk.CTkLabel(add_item_frame, text="Add New Item", font=("Arial", 14, "bold")).pack(anchor="w")

        add_row = ctk.CTkFrame(add_item_frame, fg_color="transparent")
        add_row.pack(fill="x", pady=5)
        self.inv_item_name = ctk.CTkEntry(add_row, placeholder_text="Item name (e.g. Wireless Mouse)", width=250)
        self.inv_item_name.pack(side="left", padx=5)
        self.inv_item_qty = ctk.CTkEntry(add_row, placeholder_text="Qty", width=80)
        self.inv_item_qty.pack(side="left", padx=5)
        ctk.CTkButton(add_row, text="Add Item", fg_color="green", command=self.add_inventory_item_ui).pack(side="left", padx=5)

        self.inv_status_label = ctk.CTkLabel(inv_tab, text="")
        self.inv_status_label.pack()

        # -- Borrow an item --
        borrow_frame = ctk.CTkFrame(inv_tab, fg_color="transparent")
        borrow_frame.pack(pady=10, fill="x", padx=10)
        ctk.CTkLabel(borrow_frame, text="Log a Borrow", font=("Arial", 14, "bold")).pack(anchor="w")

        borrow_row = ctk.CTkFrame(borrow_frame, fg_color="transparent")
        borrow_row.pack(fill="x", pady=5)

        self.inv_item_map = {}
        self.inv_item_dropdown = ctk.CTkOptionMenu(borrow_row, values=["No items yet"], width=200)
        self.inv_item_dropdown.pack(side="left", padx=5)
        self.inv_borrower_name = ctk.CTkEntry(borrow_row, placeholder_text="Borrower name", width=180)
        self.inv_borrower_name.pack(side="left", padx=5)
        self.inv_borrow_qty = ctk.CTkEntry(borrow_row, placeholder_text="Qty", width=60)
        self.inv_borrow_qty.pack(side="left", padx=5)
        ctk.CTkButton(borrow_row, text="Borrow", fg_color="#1f6aa5", command=self.borrow_item_ui).pack(side="left", padx=5)

        # -- Item list --
        ctk.CTkLabel(inv_tab, text="All Items", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(15, 0))
        self.inv_items_frame = ctk.CTkScrollableFrame(inv_tab, height=100)
        self.inv_items_frame.pack(fill="x", padx=10, pady=5)

        # -- Currently borrowed --
        ctk.CTkLabel(inv_tab, text="Currently Borrowed", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(15, 0))
        self.inv_active_frame = ctk.CTkScrollableFrame(inv_tab, height=150)
        self.inv_active_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.refresh_inventory_ui()

    def reset_student_password(self):
        username = self.target_user_entry.get().strip()
        user = db.get_user_by_username(username)

        if not user or user["role"] != "student":
            self.status_label.configure(text="User not found!", text_color="red")
            return

        db.reset_to_default_password(user["id"])
        self.status_label.configure(
            text=f"Reset success! New password: {db.DEFAULT_RESET_PASSWORD}",
            text_color="green"
        )
    def refresh_table(self, data=None):
        for item in self.tree.get_children(): self.tree.delete(item)
        target = data if data is not None else self.master_app.all_logs
        for entry in target:
            self.tree.insert("", "end", values=(entry['user'], entry['login'], entry['logout'], entry['duration']))

    def filter_logs(self, event):
        query = self.search_entry.get().lower()
        filtered = [log for log in self.master_app.all_logs if query in log['user'].lower()]
        self.refresh_table(filtered)

    def create_teacher(self):
        username = self.new_teacher_user.get().strip()
        password = self.new_teacher_pass.get().strip()
        full_name = self.new_teacher_name.get().strip()

        if not username or not password or not full_name:
            self.teacher_create_status.configure(text="Punan ang lahat ng kahon.", text_color="orange")
            return

        if db.get_user_by_username(username):
            self.teacher_create_status.configure(text="Username already taken.", text_color="red")
            return

        db.create_staff_user(username, password, "teacher", full_name=full_name)
        self.teacher_create_status.configure(text=f"Teacher '{full_name}' created!", text_color="green")
        self.new_teacher_user.delete(0, "end")
        self.new_teacher_pass.delete(0, "end")
        self.new_teacher_name.delete(0, "end")
        self.refresh_teacher_list()

    def refresh_teacher_list(self):
        for widget in self.teacher_list_frame.winfo_children():
            widget.destroy()

        teachers = db.get_all_teachers()
        if not teachers:
            ctk.CTkLabel(self.teacher_list_frame, text="No teachers yet.", text_color="gray").pack(pady=10)
            return

        for t in teachers:
            student_count = len(db.get_students_for_teacher(t["id"]))
            text = f"{t['full_name']} ({t['username']}) — {student_count} student(s)"
            ctk.CTkLabel(self.teacher_list_frame, text=text, anchor="w").pack(fill="x", padx=10, pady=3)

    def show_lab_occupancy(self, lab_id, lab_name):
        self.lab_occupancy_label.configure(text=f"{lab_name} — Currently Occupied")

        for widget in self.lab_occupancy_frame.winfo_children():
            widget.destroy()

        occupants = db.get_lab_occupancy(lab_id)
        if not occupants:
            ctk.CTkLabel(self.lab_occupancy_frame, text="No one is currently in this lab.",
                        text_color="gray").pack(pady=20)
            return

        for person in occupants:
            role_tag = person["role"].capitalize()
            name = person["full_name"] or person["username"]
            text = f"{name} ({role_tag}) — PC: {person['pc_name']} — Since: {person['login_time']}"
            frm = ctk.CTkFrame(self.lab_occupancy_frame)
            frm.pack(fill="x", padx=5, pady=4)
            ctk.CTkLabel(frm, text=text, anchor="w").pack(fill="x", padx=10, pady=6)

    def _get_all_connected_ips(self):
        connected = getattr(self.master_app, "connected_students", {})
        print(f"[DEBUG _get_all_connected_ips] connected_students = {connected}")
        ips = list(connected.keys())
        print(f"[DEBUG _get_all_connected_ips] IPs found: {ips}")
        return ips

    def sleep_all(self):
        ips = self._get_all_connected_ips()
        if not ips:
            print("[DEBUG sleep_all] No connected students found — nothing to send.")
        for ip in ips:
            print(f"[DEBUG sleep_all] Sending SLEEP to {ip}")
            send_command(ip, "SLEEP")

    def restart_all(self):
        for ip in self._get_all_connected_ips():
            send_command(ip, "REBOOT")

    def shutdown_all(self):
        for ip in self._get_all_connected_ips():
            send_command(ip, "SHUTDOWN")


    def add_inventory_item_ui(self):
        name = self.inv_item_name.get().strip()
        qty_str = self.inv_item_qty.get().strip()

        if not name or not qty_str.isdigit():
            self.inv_status_label.configure(text="Enter a name and a valid quantity.", text_color="orange")
            return

        existing = [i for i in db.get_all_inventory_items() if i["name"].lower() == name.lower()]
        if existing:
            self.inv_status_label.configure(text="Item already exists.", text_color="red")
            return

        db.add_inventory_item(name, int(qty_str))
        self.inv_status_label.configure(text=f"Added '{name}' (x{qty_str}).", text_color="green")
        self.inv_item_name.delete(0, "end")
        self.inv_item_qty.delete(0, "end")
        self.refresh_inventory_ui()

    def borrow_item_ui(self):
        selected = self.inv_item_dropdown.get()
        item_id = self.inv_item_map.get(selected)
        borrower = self.inv_borrower_name.get().strip()
        qty_str = self.inv_borrow_qty.get().strip()

        if not item_id or not borrower or not qty_str.isdigit():
            self.inv_status_label.configure(text="Fill in item, borrower, and quantity.", text_color="orange")
            return

        ok, err = db.borrow_item(item_id, borrower, int(qty_str))
        if ok:
            self.inv_status_label.configure(text=f"'{borrower}' borrowed {qty_str}x {selected}.", text_color="green")
            self.inv_borrower_name.delete(0, "end")
            self.inv_borrow_qty.delete(0, "end")
        else:
            self.inv_status_label.configure(text=err, text_color="red")
        self.refresh_inventory_ui()

    def return_item_ui(self, borrow_id):
        db.return_item(borrow_id)
        self.refresh_inventory_ui()

    def refresh_inventory_ui(self):
        for widget in self.inv_items_frame.winfo_children():
            widget.destroy()
        for widget in self.inv_active_frame.winfo_children():
            widget.destroy()

        items = db.get_all_inventory_items()
        self.inv_item_map = {i["name"]: i["id"] for i in items}
        if items:
            self.inv_item_dropdown.configure(values=list(self.inv_item_map.keys()))
            self.inv_item_dropdown.set(list(self.inv_item_map.keys())[0])
        else:
            self.inv_item_dropdown.configure(values=["No items yet"])
            self.inv_item_dropdown.set("No items yet")

        if not items:
            ctk.CTkLabel(self.inv_items_frame, text="No items added yet.", text_color="gray").pack(pady=10)
        for item in items:
            text = f"{item['name']} — {item['quantity_available']} / {item['quantity_total']} available"
            ctk.CTkLabel(self.inv_items_frame, text=text, anchor="w").pack(fill="x", padx=10, pady=3)

        active = db.get_active_borrows()
        if not active:
            ctk.CTkLabel(self.inv_active_frame, text="Nothing currently borrowed.", text_color="gray").pack(pady=10)
        for record in active:
            frm = ctk.CTkFrame(self.inv_active_frame)
            frm.pack(fill="x", padx=5, pady=4)
            text = f"{record['item_name']} x{record['quantity']} — {record['borrower_name']} (since {record['borrowed_at']})"
            ctk.CTkLabel(frm, text=text, anchor="w").pack(side="left", padx=10, pady=6, fill="x", expand=True)
            ctk.CTkButton(frm, text="Mark Returned", fg_color="green", width=110,
                        command=lambda bid=record["id"]: self.return_item_ui(bid)).pack(side="right", padx=10)