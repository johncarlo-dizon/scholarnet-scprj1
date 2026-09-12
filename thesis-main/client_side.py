import socket
import threading
import customtkinter as ctk
import datetime

# Configuration
TEACHER_IP = "192.168.100.71" # IP ng Teacher PC
LOG_PORT = 5001

class LoginWindow(ctk.CTk):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.title("Student Login")
        self.geometry("300x250")
        
        ctk.CTkLabel(self, text="Username").pack(pady=10)
        self.user_entry = ctk.CTkEntry(self)
        self.user_entry.pack(pady=5)
        
        ctk.CTkButton(self, text="Login", command=self.attempt_login).pack(pady=20)

    def attempt_login(self):
        user = self.user_entry.get()
        if user:
            # Send login info to Teacher PC
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((TEACHER_IP, LOG_PORT))
                s.sendall(f"USER: {user} | PC: {socket.gethostname()} | Time: {datetime.datetime.now().strftime('%H:%M:%S')}".encode())
                s.close()
            except:
                print("Cannot connect to Teacher for logging")
            self.callback()
            self.destroy()

class ClientApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Student Terminal")
        self.geometry("300x200")
        self.lock_window = None
        ctk.CTkLabel(self, text="System Online").pack(pady=50)
        threading.Thread(target=self.start_listener, daemon=True).start()

    def start_listener(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("0.0.0.0", 5000))
        server.listen(5)
        while True:
            conn, addr = server.accept()
            command = conn.recv(1024).decode()
            if command == "LOCK": self.after(0, self.show_lock)
            elif command == "UNLOCK": self.after(0, self.hide_lock)
            conn.close()

    def show_lock(self):
        if not self.lock_window:
            self.lock_window = ctk.CTkToplevel(self)
            self.lock_window.attributes("-fullscreen", True)
            self.lock_window.attributes("-topmost", True)
            ctk.CTkLabel(self.lock_window, text="TERMINAL LOCKED", font=("Arial", 80, "bold"), text_color="red").pack(expand=True)

    def hide_lock(self):
        if self.lock_window:
            self.lock_window.destroy()
            self.lock_window = None

def run_app():
    app = ClientApp()
    app.mainloop()

if __name__ == "__main__":
    login = LoginWindow(callback=run_app)
    login.mainloop()