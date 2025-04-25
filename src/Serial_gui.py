import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
import tkinter as tk
import serial
import serial.tools.list_ports
import threading
import re
import os
import glob
import sys

END_CHAR_OPTIONS = {
    "None": "",
    "CR (Carriage Return)": "0D",
    "LF (Line Feed)": "0A",
    "CR + LF": "0D0A",
    "LF + CR": "0A0D",
    "NULL": "00"
}
DISPLAY_FORMATS = ["ASCII", "HEX", "HEX + ASCII", "DEC"]

def find_commands_file():
    files = glob.glob("*_commands.h")
    if not files:
        tk.messagebox.showerror("Error", "No *_commands.h file found in this directory.")
        sys.exit(1)
    return files[0]

def parse_groups(filepath):
    groups = {}
    current_group = None
    current_type = None
    blank_lines = 0

    with open(filepath, "r") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
                continue
            else:
                if blank_lines >= 2:
                    current_group = None
                    current_type = None
                blank_lines = 0

            comment_match = re.match(r"//\s*(.+)", line)
            define_match = re.match(r"#define\s+(\w+)\s+0x([0-9A-Fa-f]+)", line)

            if comment_match:
                text = comment_match.group(1).strip()
                if "command" in text.lower():
                    base_name = text.lower().replace("ack", "").replace("commands", "").replace("command", "").strip().title()
                    if base_name not in groups:
                        groups[base_name] = {"commands": [], "acks": []}
                    current_group = base_name
                    current_type = "acks" if "ack" in text.lower() else "commands"
            elif define_match and current_group:
                name, hex_val = define_match.groups()
                groups[current_group][current_type].append((name, int(hex_val, 16)))

    return groups

class SerialApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Command Sender")

        self.commands_file = find_commands_file()
        self.groups_data = parse_groups(self.commands_file)
        self.filtered_data = self.groups_data.copy()

        self.serial_conn = None
        self.baud_rate = ttk.StringVar(value="9600")
        self.port = ttk.StringVar()
        self.end_char = ttk.StringVar(value="0D")
        self.end_char_option = ttk.StringVar(value="CR (Carriage Return)")
        self.auto_scroll = ttk.BooleanVar(value=True)
        self.display_format = ttk.StringVar(value="HEX + ASCII")
        self.search_text = tk.StringVar()

        self.setup_ui()

    def setup_ui(self):
        top = ttk.Frame(self.root)
        top.pack(padx=10, pady=5, fill=X)

        ttk.Label(top, text="Baud Rate:").grid(row=0, column=0)
        ttk.Combobox(top, textvariable=self.baud_rate,
                     values=["9600", "19200", "38400", "57600", "115200"], width=10).grid(row=0, column=1)

        ttk.Label(top, text="COM Port:").grid(row=0, column=2)
        self.port_combo = ttk.Combobox(top, textvariable=self.port,
                                       values=self.get_ports(), width=10)
        self.port_combo.grid(row=0, column=3)
        ttk.Button(top, text="⟳", command=self.refresh_ports).grid(row=0, column=4)

        ttk.Label(top, text="End Char:").grid(row=0, column=5)
        end_combo = ttk.Combobox(top, textvariable=self.end_char_option,
                                 values=list(END_CHAR_OPTIONS.keys()), width=18)
        end_combo.grid(row=0, column=6)
        end_combo.bind("<<ComboboxSelected>>", self.update_end_char)

        self.end_char_label = ttk.Label(top, text="Hex: 0x0D")
        self.end_char_label.grid(row=0, column=7, padx=5)

        ttk.Button(top, text="Connect", command=self.connect).grid(row=0, column=8)
        ttk.Button(top, text="Disconnect", command=self.disconnect).grid(row=0, column=9)

        self.output = ScrolledText(self.root, height=10, autohide=True)
        self.output.pack(padx=10, fill=X)
        self.output.text.config(state="disabled")

        monitor_controls = ttk.Frame(self.root)
        monitor_controls.pack(padx=10, pady=(5, 10), fill=X)
        ttk.Label(monitor_controls, text="Display Format:").pack(side=LEFT)
        ttk.Combobox(monitor_controls, textvariable=self.display_format,
                     values=DISPLAY_FORMATS, width=15).pack(side=LEFT, padx=(5, 20))
        ttk.Label(monitor_controls, text="Auto Scroll:").pack(side=LEFT)
        ttk.Checkbutton(monitor_controls, variable=self.auto_scroll).pack(side=LEFT)
        ttk.Button(monitor_controls, text="Clear Output", command=self.clear_log).pack(side=RIGHT)

        search_frame = ttk.Frame(self.root)
        search_frame.pack(padx=10, pady=(0, 5), fill=X)
        ttk.Label(search_frame, text="Search Commands:").pack(side=LEFT)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_text)
        search_entry.pack(side=LEFT, fill=X, expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self.filter_commands())

        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=BOTH, expand=True)

        self.command_canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.command_canvas.yview)
        self.command_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        self.command_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.command_frame = ttk.Frame(self.command_canvas)
        self.command_canvas.create_window((0, 0), window=self.command_frame, anchor="nw")
        self.command_frame.bind("<Configure>", lambda e: self.command_canvas.configure(scrollregion=self.command_canvas.bbox("all")))

        self.render_command_groups()

    def filter_commands(self):
        query = self.search_text.get().lower()
        if not query:
            self.filtered_data = self.groups_data.copy()
        else:
            self.filtered_data = {}
            for group, data in self.groups_data.items():
                cmds = [c for c in data["commands"] if query in c[0].lower()]
                acks = [a for a in data["acks"] if query in a[0].lower()]
                if cmds or acks:
                    self.filtered_data[group] = {"commands": cmds, "acks": acks}
        self.render_command_groups()

    def render_command_groups(self):
        for widget in self.command_frame.winfo_children():
            widget.destroy()
        for group, data in self.filtered_data.items():
            self.create_group_section(self.command_frame, group, data["commands"], data["acks"])

    def create_group_section(self, parent, title, commands, acks):
        container = ttk.Frame(parent)
        container.pack(fill=X, padx=10, pady=5)

        header = ttk.Label(container, text="▶ " + title, cursor="hand2", font=("Segoe UI", 10, "bold"))
        header.pack(anchor="w")

        body = ttk.Frame(container)
        body.pack(fill=X, padx=20, pady=2)
        body.pack_forget()

        def toggle():
            if body.winfo_ismapped():
                body.pack_forget()
                header.config(text="▶ " + title)
            else:
                body.pack(fill=X, padx=20, pady=2)
                header.config(text="▼ " + title)

        header.bind("<Button-1>", lambda e: toggle())

        ttk.Label(body, text="Command", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="ACK Response", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(20, 0))

        max_len = max(len(commands), len(acks))
        for i in range(max_len):
            if i < len(commands):
                name, val = commands[i]
                ttk.Label(body, text=f"{name} (0x{val:02X})").grid(row=i+1, column=0, sticky="w", padx=5)
                ttk.Button(body, text="Send", command=lambda v=val: self.send_command(v)).grid(row=i+1, column=1, padx=5)
            if i < len(acks):
                name, val = acks[i]
                ttk.Label(body, text=f"{name} (0x{val:02X})").grid(row=i+1, column=2, sticky="w", padx=(20, 0))

    def update_end_char(self, event=None):
        val = self.end_char_option.get()
        self.end_char.set(END_CHAR_OPTIONS[val])
        self.end_char_label.config(text=f"Hex: 0x{self.end_char.get() if self.end_char.get() else 'None'}")

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def refresh_ports(self):
        self.port_combo["values"] = self.get_ports()

    def connect(self):
        try:
            self.serial_conn = serial.Serial(self.port.get(), int(self.baud_rate.get()), timeout=1)
            threading.Thread(target=self.read_serial, daemon=True).start()
            self.log("Connected to serial port.")
        except Exception as e:
            self.log(f"Connection error: {e}")

    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            self.log("Disconnected.")

    def send_command(self, value):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                end = bytes.fromhex(self.end_char.get()) if self.end_char.get() else b""
                self.serial_conn.write(bytes([value]) + end)
                self.log(f"Sent: {self.format_bytes(bytes([value]) + end)}")
            except Exception as e:
                self.log(f"Send error: {e}")
        else:
            self.log("Serial port not open.")

    def read_serial(self):
        while self.serial_conn and self.serial_conn.is_open:
            try:
                line = self.serial_conn.readline()
                if line:
                    self.log(f"Received: {self.format_bytes(line)}")
            except:
                break

    def format_bytes(self, data):
        fmt = self.display_format.get()
        if fmt == "ASCII":
            return data.decode(errors="replace")
        elif fmt == "HEX":
            return data.hex(" ").upper()
        elif fmt == "DEC":
            return " ".join(str(b) for b in data)
        else:
            hex_part = data.hex(" ").upper()
            ascii_part = data.decode(errors="replace").replace("\r", "\\r").replace("\n", "\\n")
            return f"{hex_part}  ({ascii_part})"

    def log(self, text):
        self.output.text.config(state="normal")
        self.output.text.insert("end", text + "\n")
        self.output.text.config(state="disabled")
        if self.auto_scroll.get():
            self.output.text.yview("end")

    def clear_log(self):
        self.output.text.config(state="normal")
        self.output.text.delete("1.0", "end")
        self.output.text.config(state="disabled")

if __name__ == "__main__":
    app = ttk.Window(themename="darkly")
    SerialApp(app)
    app.mainloop()