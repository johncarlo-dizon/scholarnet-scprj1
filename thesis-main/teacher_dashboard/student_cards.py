import customtkinter as ctk


def setup_grid_layout(self):
    self.grid_frame = ctk.CTkScrollableFrame(self, label_text="Lab Monitoring Grid", height=400)
    self.grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
    self.grid_frame.grid_columnconfigure((0, 1, 2), weight=1)


def build_card_label(pc_number, full_name, expression, role="student"):
    if role == "teacher":
        return f"TEACHER - {full_name}"
    return f"PC {pc_number} - {full_name} - {expression}"


def create_student_card(self, ip, index, pc_number, full_name, expression="Waiting...", role="student"):
    if ip in self.student_cards:
        return

    row = index // 3
    col = index % 3

    label = build_card_label(pc_number, full_name, expression, role)

    pc_card = ctk.CTkFrame(self.grid_frame, corner_radius=10, border_width=1)
    pc_card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")

    screen_preview = ctk.CTkFrame(pc_card, height=160, corner_radius=6)
    screen_preview.pack(fill="x", padx=10, pady=10)
    screen_preview.pack_propagate(False)

    lbl_preview = ctk.CTkLabel(screen_preview, text=f"{label}\n(Waiting for Live Stream...)", text_color="#888888", font=ctk.CTkFont(size=11))
    lbl_preview.pack(fill="both", expand=True)

    lbl_preview.bind("<Button-3>", lambda e: self.show_context_menu(e, ip, label))
    screen_preview.bind("<Button-3>", lambda e: self.show_context_menu(e, ip, label))

    lbl_info_text = ctk.CTkLabel(pc_card, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color=("black", "white"))
    lbl_info_text.pack(pady=(0, 10))
    lbl_info_text.bind("<Button-3>", lambda e: self.show_context_menu(e, ip, label))

    self.student_cards[ip] = {
        "card": pc_card,
        "frame": pc_card,
        "preview": lbl_preview,
        "info_label": lbl_info_text,
        "pc_number": pc_number,
        "full_name": full_name,
        "expression": expression,
        "role": role,
    }