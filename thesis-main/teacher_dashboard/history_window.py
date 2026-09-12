import customtkinter as ctk
import tkinter.ttk as ttk

def open_history_window(master, login_history_data):
    history_win = ctk.CTkToplevel(master)
    history_win.title("Student Login & Logout History")
    history_win.geometry("750x450")
   
    lbl_title = ctk.CTkLabel(history_win, text="Lab User Session History", font=ctk.CTkFont(size=16, weight="bold"))
    lbl_title.pack(pady=10)
   
    table_frame = ctk.CTkFrame(history_win)
    table_frame.pack(fill="both", expand=True, padx=20, pady=10)
   
    columns = ("Name", "IP Address", "Login Time", "Logout Time", "Duration")
    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
   
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=130, anchor="center")
       
    tree.pack(side="left", fill="both", expand=True)
   
    for item in login_history_data:
        tree.insert("", "end", values=(item["name"], item["ip"], item["login"], item["logout"], item["duration"]))