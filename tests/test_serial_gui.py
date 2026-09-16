import time
import unittest
from unittest.mock import patch

import serial
from serial_command_sender import gui as Serial_gui


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Serial_gui.ttk.Window(themename="darkly")
        cls.root.withdraw()
        cls.app = Serial_gui.SerialApp(cls.root)

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
        self.assertIn('Decoded return message: "MIXER_STARTED"', decoded)
        self.assertIn('Decoded return message: "MIXER_STOPPED"', decoded)
        app.clear_log()
        self.assertEqual(app.output.text.get("1.0", "end-1c"), "")
        self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"), "")
        old_session = app.session
        app.disconnect()
        self.assertFalse(app.reader.is_alive())
        app.events.put((old_session, "data", b"\x81"))
        connection = serial.serial_for_url("loop://", timeout=0.1, write_timeout=1)
        with patch.object(Serial_gui.serial, "Serial", return_value=connection):
            app.connect()
        app.root.after_cancel(app.poll_id)
        app.process_events()
        self.assertEqual(app.decoded_output.text.get("1.0", "end-1c"), "")
        app.disconnect()


if __name__ == "__main__":
    unittest.main()
