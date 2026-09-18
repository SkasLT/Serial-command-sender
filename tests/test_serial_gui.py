import time
import unittest
import tempfile
from pathlib import Path
from importlib.resources import files
from datetime import datetime
from unittest.mock import patch

import serial
from serial_command_sender import gui as Serial_gui


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Serial_gui.ttk.Window(themename="darkly")
        cls.root.withdraw()
        cls.app = Serial_gui.SerialApp(cls.root, files("serial_command_sender.data").joinpath("My_device_commands.h"))

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def test_loopback_receive_clear_and_reconnect(self):
        app = self.app
        app.port.set("test")
        connection = serial.serial_for_url("loop://", timeout=0.1, write_timeout=1)
        with patch.object(Serial_gui.serial, "Serial", return_value=connection) as constructor:
            app.connect()
            app.connect()
            constructor.assert_called_once()
        # Loopback returns the sent raw ACK bytes through the real reader thread.
        app.send_command("8182")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            self.root.update()
            if "MIXER_STOPPED" in app.decoded_output.text.get("1.0", "end"):
                break
            time.sleep(0.01)
        decoded = app.decoded_output.text.get("1.0", "end")
        self.assertRegex(app.output.text.get("1.0", "end"),
                         r"\[(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\] Sent: ")
        self.assertIn('Decoded return message: "MIXER_STARTED"', decoded)
        self.assertIn('Decoded return message: "MIXER_STOPPED"', decoded)
        app.clear_log()
        self.assertEqual(app.output.text.get("1.0", "end-1c"), "")
        self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"), "")
        old_session = app.session
        app.disconnect()
        self.assertFalse(app.reader.is_alive())
        app.events.put((old_session, "data", b"\x81", datetime.now()))
        connection = serial.serial_for_url("loop://", timeout=0.1, write_timeout=1)
        with patch.object(Serial_gui.serial, "Serial", return_value=connection):
            app.connect()
        app.root.after_cancel(app.poll_id)
        app.process_events()
        self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"), "")
        app.disconnect()

    def test_receive_and_idle_decoding_keep_arrival_time(self):
        app = self.app
        received_at = datetime(2026, 9, 18, 23, 59, 59)
        displayed_at = datetime(2026, 9, 19, 0, 0, 2)
        try:
            for mode, data in [("Raw bytes", b"\x81"), ("DEC text", b"129")]:
                with self.subTest(mode=mode):
                    app.clear_log()
                    app.decoder.mode = mode
                    app.events.put((app.session, "data", data, received_at))
                    with patch.object(Serial_gui, "datetime") as clock:
                        clock.now.return_value = displayed_at
                        app.root.after_cancel(app.poll_id)
                        app.process_events()
                        if mode == "DEC text":
                            self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"), "")
                            app.last_received -= 1
                            app.root.after_cancel(app.poll_id)
                            app.process_events()
                        app.log("Status")
                    traffic = app.output.text.get("1.0", "end-1c")
                    self.assertTrue(traffic.startswith("[23:59:59] Received: "))
                    self.assertIn("[00:00:02] Status", traffic)
                    self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"),
                                     '[23:59:59] Decoded return message: "MIXER_STARTED"\n')
        finally:
            app.decoder.mode = "Raw bytes"
            app.clear_log()

    def test_load_header_after_empty_startup(self):
        window = Serial_gui.tk.Toplevel(self.root)
        window.withdraw()
        with patch.object(Serial_gui, "find_commands_file", return_value=None):
            app = Serial_gui.SerialApp(window)
        try:
            self.assertIsNone(app.commands_file)
            self.assertEqual(app.loaded_file.get(), "No command file loaded.")
            with tempfile.TemporaryDirectory() as folder:
                header = Path(folder) / "custom.h"
                header.write_text("// Device commands\n#define START 1\n"
                                  "// Device ack commands\n#define READY 0x8101\n")
                with patch.object(Serial_gui.filedialog, "askopenfilename", return_value=str(header)):
                    self.assertTrue(app.load_command_file())
                self.assertEqual(app.commands_file, header.resolve())
                self.assertIn(str(header.resolve()), app.loaded_file.get())
                self.assertEqual(app.decoder.feed(b"\x81\x01"), ["READY"])
                self.assertTrue(app.command_frame.winfo_children())
                app.search_text.set("START")
                app.filter_commands()
                app.port.set("test")
                connection = serial.serial_for_url("loop://", timeout=0.1)
                with patch.object(Serial_gui.serial, "Serial", return_value=connection):
                    app.connect()
                invalid = Path(folder) / "invalid.h"
                invalid.write_text("not a command header")
                with patch.object(Serial_gui.messagebox, "showerror") as error:
                    self.assertFalse(app.load_command_file(invalid))
                    error.assert_called_once()
                with patch.object(Serial_gui.filedialog, "askopenfilename", return_value=""):
                    self.assertFalse(app.load_command_file())
                self.assertTrue(connection.is_open)
                self.assertEqual(app.commands_file, header.resolve())
                app.decoder.feed(b"\x81")
                previous_session = app.session
                header.write_text("// Other commands\n#define STOP 2\n"
                                  "// Other ack commands\n#define STOPPED 0x82\n")
                app.receive_mode.set("HEX text")
                self.assertTrue(app.load_command_file(header))
                self.assertFalse(connection.is_open)
                self.assertGreater(app.session, previous_session)
                self.assertEqual(app.search_text.get(), "")
                self.assertEqual(app.decoder.buffer, b"")
                self.assertEqual(app.decoder.feed(b"82\n"), ["STOPPED"])
                self.assertNotIn("Device", app.groups_data)
                app.clear_log()
                self.assertIn(str(header.resolve()), app.loaded_file.get())
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()
