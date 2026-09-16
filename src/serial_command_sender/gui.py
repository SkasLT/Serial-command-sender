import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
import tkinter as tk
from tkinter import messagebox
import serial
import serial.tools.list_ports
import threading
import argparse
from pathlib import Path
import queue
import time
from .ack_decoder import AckDecoder, parse_groups
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

def find_commands_file(filepath=None):
    if filepath is not None:
        path = Path(filepath).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"Command header does not exist: {path}")
        return path
    frozen = getattr(sys, "frozen", False)
    directory = Path(sys.executable).parent if frozen else Path.cwd()
    files = sorted(directory.glob("*_commands.h"))
    if not files and not frozen:
        return Path(__file__).resolve().parent / "data" / "My_device_commands.h"
    if len(files) != 1:
        raise ValueError(f"Expected exactly one *_commands.h file in {directory}; found {len(files)}.")
    return files[0]

class SerialApp:
    def __init__(self, root, commands_file=None):
        self.root = root
        self.root.title("Serial Command Sender")

        self.commands_file = find_commands_file(commands_file)
        self.groups_data = parse_groups(self.commands_file)
        self.filtered_data = self.groups_data.copy()

        self.serial_conn = None
        self.events = queue.Queue(maxsize=1000)
        self.reader_stop = threading.Event()
        self.reader = None
        self.session = 0
        self.last_received = 0
        self.decoder = AckDecoder(self.groups_data)
        self.receive_mode = tk.StringVar(value="Raw bytes")
        self.baud_rate = ttk.StringVar(value="9600")
        self.port = ttk.StringVar()
        self.end_char = ttk.StringVar(value="0D")
        self.end_char_option = ttk.StringVar(value="CR (Carriage Return)")
        self.auto_scroll = ttk.BooleanVar(value=True)
        self.display_format = ttk.StringVar(value="HEX + ASCII")
        self.search_text = tk.StringVar()

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_id = self.root.after(30, self.process_events)
        self.log(f"Header: {self.commands_file}")

    def setup_ui(self):
        top = ttk.Frame(self.root)
        top.pack(padx=10, pady=5, fill=X)

        ttk.Label(top, text="Baud Rate:").grid(row=0, column=0)
        ttk.Combobox(
            top,
            textvariable=self.baud_rate,
            values=["9600", "19200", "38400", "57600", "115200"],
            width=10,
        ).grid(row=0, column=1)

        ttk.Label(top, text="COM Port:").grid(row=0, column=2)
        self.port_combo = ttk.Combobox(
            top, textvariable=self.port, values=self.get_ports(), width=10
        )
        self.port_combo.grid(row=0, column=3)
        ttk.Button(top, text="Refresh", command=self.refresh_ports).grid(row=0, column=4)

        ttk.Label(top, text="End Char:").grid(row=0, column=5)
        end_combo = ttk.Combobox(
            top,
            textvariable=self.end_char_option,
            values=list(END_CHAR_OPTIONS.keys()),
            width=18, state="readonly",
        )
        end_combo.grid(row=0, column=6)
        end_combo.bind("<<ComboboxSelected>>", self.update_end_char)

        self.end_char_label = ttk.Label(top, text="Hex: 0x0D")
        self.end_char_label.grid(row=0, column=7, padx=5)

        ttk.Button(top, text="Connect", command=self.connect).grid(row=0, column=8)
        ttk.Button(top, text="Disconnect", command=self.disconnect).grid(row=0, column=9)

        self.output = ScrolledText(self.root, height=10, autohide=True)
        self.output.pack(padx=10, fill=X)
        self.output.text.config(state="disabled")

        self.decoded_output = ScrolledText(self.root, height=4, autohide=True)
        self.decoded_output.pack(padx=10, pady=(5, 0), fill=X)
        self.decoded_output.text.config(state="disabled")
        receive_controls = ttk.Frame(self.root)
        receive_controls.pack(padx=10, pady=5, fill=X)
        ttk.Label(receive_controls, text="Receive encoding:").pack(side=LEFT)
        receive_combo = ttk.Combobox(receive_controls, textvariable=self.receive_mode,
                                     values=AckDecoder.MODES, state="readonly", width=15)
        receive_combo.pack(side=LEFT, padx=5)
        receive_combo.bind("<<ComboboxSelected>>", self.change_receive_mode)

        monitor_controls = ttk.Frame(self.root)
        monitor_controls.pack(padx=10, pady=(5, 10), fill=X)
        ttk.Label(monitor_controls, text="Display Format:").pack(side=LEFT)
        ttk.Combobox(
            monitor_controls,
            textvariable=self.display_format,
            values=DISPLAY_FORMATS,
            width=15, state="readonly",
        ).pack(side=LEFT, padx=(5, 20))
        ttk.Label(monitor_controls, text="Auto Scroll:").pack(side=LEFT)
        ttk.Checkbutton(monitor_controls, variable=self.auto_scroll).pack(side=LEFT)
        ttk.Button(
            monitor_controls, text="Clear Output", command=self.clear_log
        ).pack(side=RIGHT)

        search_frame = ttk.Frame(self.root)
        search_frame.pack(padx=10, pady=(0, 5), fill=X)
        ttk.Label(search_frame, text="Search Commands:").pack(side=LEFT)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_text)
        search_entry.pack(side=LEFT, fill=X, expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self.filter_commands())

        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=BOTH, expand=True)

        self.command_canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.command_canvas.yview
        )
        self.command_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        self.command_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.command_frame = ttk.Frame(self.command_canvas)
        self.command_canvas.create_window(
            (0, 0), window=self.command_frame, anchor="nw"
        )
        self.command_frame.bind(
            "<Configure>",
            lambda e: self.command_canvas.configure(
                scrollregion=self.command_canvas.bbox("all")
            ),
        )

        self.render_command_groups()
        self.scroll_areas = {
            self.output: self.output.text,
            self.decoded_output: self.decoded_output.text,
            canvas_frame: self.command_canvas,
        }
        self.wheel_tag = f"SerialMouseWheel{id(self)}"
        self.wheel_target = None
        self.wheel_remainder = 0.0
        self.window_system = self.root.tk.call("tk", "windowingsystem")
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_class(self.wheel_tag, sequence, self.scroll_with_mousewheel)
        self.add_wheel_bindings(self.root)

    def add_wheel_bindings(self, widget):
        # Run before native Text/Combobox bindings to avoid scrolling twice.
        tags = widget.bindtags()
        if self.wheel_tag not in tags:
            widget.bindtags((self.wheel_tag,) + tags)
        for child in widget.winfo_children():
            self.add_wheel_bindings(child)

    def scroll_with_mousewheel(self, event):
        # Windows can deliver wheel events to the focused widget. Route using
        # pointer coordinates so a different panel never scrolls by accident.
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget not in self.scroll_areas:
            widget = widget.master
        if widget is None:
            return
        target = self.scroll_areas[widget]
        if target is not self.wheel_target:
            self.wheel_target = target
            self.wheel_remainder = 0.0
        if event.num in (4, 5):
            amount = -3 if event.num == 4 else 3
        elif self.window_system == "aqua":
            amount = -event.delta
        else:
            amount = -event.delta / 120 * 3
        self.wheel_remainder += amount
        units = int(self.wheel_remainder)
        self.wheel_remainder -= units
        if units and target.yview() != (0.0, 1.0):
            target.yview_scroll(units, "units")
        return "break"

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
            self.create_group_section(
                self.command_frame, group, data["commands"], data["acks"]
            )
        if hasattr(self, "wheel_tag"):
            self.add_wheel_bindings(self.command_frame)

    def create_group_section(self, parent, title, commands, acks):
        container = ttk.Frame(parent)
        container.pack(fill=X, padx=10, pady=5)

        header = ttk.Label(
            container,
            text="▶ " + title,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
        )
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

        ttk.Label(
            body, text="Command", font=("Segoe UI", 9, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="ACK Response",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=0, column=2, sticky="w", padx=(20, 0))

        max_len = max(len(commands), len(acks))
        for i in range(max_len):
            if i < len(commands):
                name, hex_str = commands[i]
                ttk.Label(
                    body, text=f"{name} (0x{hex_str.upper()})"
                ).grid(row=i + 1, column=0, sticky="w", padx=5)
                ttk.Button(
                    body, text="Send", command=lambda v=hex_str: self.send_command(v)
                ).grid(row=i + 1, column=1, padx=5)
            if i < len(acks):
                name, hex_str = acks[i]
                ttk.Label(
                    body, text=f"{name} (0x{hex_str.upper()})"
                ).grid(row=i + 1, column=2, sticky="w", padx=(20, 0))

    def update_end_char(self, event=None):
        val = self.end_char_option.get()
        self.end_char.set(END_CHAR_OPTIONS[val])
        self.end_char_label.config(
            text=f"Hex: 0x{self.end_char.get() if self.end_char.get() else 'None'}"
        )

    def get_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def refresh_ports(self):
        self.port_combo["values"] = self.get_ports()

    def connect(self):
        if self.serial_conn is not None:
            self.log("Already connected. Disconnect before changing ports.")
            return
        try:
            if not self.port.get().strip() or int(self.baud_rate.get()) <= 0:
                raise ValueError("Select a COM port and a positive baud rate.")
            connection = serial.Serial(self.port.get(), int(self.baud_rate.get()),
                                       timeout=0.1, write_timeout=1)
            self.serial_conn = connection
            self.session += 1
            self.decoder.reset()
            self.reader_stop = threading.Event()
            self.reader = threading.Thread(target=self.read_serial,
                args=(connection, self.reader_stop, self.session), daemon=True)
            self.reader.start()
            self.log(f"Connected to {self.port.get()} at {self.baud_rate.get()} baud.")
        except (ValueError, serial.SerialException, OSError) as error:
            self.log(f"Connection error: {error}")

    def disconnect(self):
        self.reader_stop.set()
        connection = self.serial_conn
        self.serial_conn = None
        self.session += 1
        if connection:
            try:
                connection.close()
            except (serial.SerialException, OSError) as error:
                self.log(f"Close error: {error}")
            self.log("Disconnected.")
        if self.reader:
            self.reader.join(timeout=0.3)
        self.decoder.reset()

    def close(self):
        self.disconnect()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()

    def change_receive_mode(self, event=None):
        self.decoder.reset()
        self.decoder.mode = self.receive_mode.get()
        self.log(f"Receive encoding: {self.decoder.mode}")

    def send_command(self, value_hex):
        """
        Send command where value_hex is the hex part from the header (e.g. '80', '0001', '0601').
        - 1-byte values (like '80') -> one byte
        - 2-byte values (like '0001', '0601', 'AABB') -> two bytes [AA, BB]
        Then append the selected end character.
        """
        if self.serial_conn and self.serial_conn.is_open:
            try:
                hex_str = str(value_hex).strip()

                # Allow '0x' prefix just in case
                if hex_str.lower().startswith("0x"):
                    hex_str = hex_str[2:]

                if len(hex_str) == 0:
                    self.log("Empty command value.")
                    return

                # Pad to even number of hex digits so fromhex can parse
                if len(hex_str) % 2 == 1:
                    hex_str = "0" + hex_str

                # Interpret hex string as sequence of bytes
                cmd_bytes = bytes.fromhex(hex_str)

                end = bytes.fromhex(self.end_char.get()) if self.end_char.get() else b""
                payload = cmd_bytes + end

                self.serial_conn.write(payload)
                self.log(f"Sent: {self.format_bytes(payload)}")
            except Exception as e:
                self.log(f"Send error: {e}")
        else:
            self.log("Serial port not open.")

    def read_serial(self, connection, stop, session):
        # This worker never accesses Tk widgets or Tk variables.
        while not stop.is_set():
            try:
                data = connection.read(min(connection.in_waiting or 1, 4096))
                if not data:
                    continue
                event = (session, "data", data)
            except (serial.SerialException, OSError) as error:
                if stop.is_set():
                    return
                event = (session, "error", str(error))
            while not stop.is_set():
                try:
                    self.events.put(event, timeout=0.1)
                    break
                except queue.Full:
                    continue
            if event[1] == "error":
                return

    def process_events(self):
        for _ in range(100):
            try:
                session, kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if session != self.session:
                continue
            if kind == "error":
                self.log(f"Receive error: {value}")
                self.disconnect()
            else:
                self.log(f"Received: {self.format_bytes(value)}")
                self.show_decoded(self.decoder.feed(value))
                self.last_received = time.monotonic()
        if self.events.empty() and self.decoder.buffer and time.monotonic() - self.last_received >= 0.3:
            self.show_decoded(self.decoder.feed(final=True))
        self.poll_id = self.root.after(30, self.process_events)

    def show_decoded(self, messages):
        for message in messages:
            self.append_output(self.decoded_output.text, f'Decoded return message: "{message}"')

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
            ascii_part = (
                data.decode(errors="replace")
                .replace("\r", "\\r")
                .replace("\n", "\\n")
            )
            return f"{hex_part}  ({ascii_part})"

    def append_output(self, widget, text):
        widget.config(state="normal")
        widget.insert("end", text + "\n")
        # Bound history so a long-running monitor does not grow indefinitely.
        lines = int(widget.index("end-1c").split(".")[0])
        if lines > 2000:
            widget.delete("1.0", f"{lines - 2000 + 1}.0")
        widget.config(state="disabled")
        if self.auto_scroll.get():
            widget.see("end")

    def log(self, text):
        self.append_output(self.output.text, text)

    def clear_log(self):
        for widget in (self.output.text, self.decoded_output.text):
            widget.config(state="normal")
            widget.delete("1.0", "end")
            widget.config(state="disabled")
        self.decoder.reset()

def main(argv=None):
    parser = argparse.ArgumentParser(description="Send serial commands and decode ACK replies.")
    parser.add_argument("--commands", type=Path, help="Path to the device command header")
    args = parser.parse_args(argv)
    app = ttk.Window(themename="darkly")
    try:
        SerialApp(app, args.commands)
    except (OSError, ValueError) as error:
        messagebox.showerror("Cannot load command header", str(error), parent=app)
        app.destroy()
        return 1
    else:
        app.mainloop()
    return 0
