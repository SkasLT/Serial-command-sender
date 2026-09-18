"""Check installed metadata, packaged data, and header discovery."""
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from serial_command_sender.gui import find_commands_file


class PackagingTests(unittest.TestCase):
    def test_installed_entry_point_and_example(self):
        package = distribution("serial-command-sender")
        entries = {entry.name: entry.value for entry in package.entry_points
                   if entry.group == "gui_scripts"}
        self.assertEqual(entries["serial-command-sender"], "serial_command_sender.gui:main")
        example = files("serial_command_sender").joinpath("data/My_device_commands.h")
        self.assertIn("MIXER_STARTED", example.read_text(encoding="utf-8"))

    def test_python_header_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with patch("serial_command_sender.gui.Path.cwd", return_value=directory):
                self.assertIsNone(find_commands_file())
                custom = directory / "Device_commands.h"
                custom.write_text("// Device commands\n#define START 1\n")
                self.assertEqual(find_commands_file(), custom)
                second = directory / "Other_commands.h"
                second.write_text(custom.read_text())
                self.assertIsNone(find_commands_file())
                self.assertEqual(find_commands_file(custom), custom.resolve())

    def test_frozen_can_start_without_external_header(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with patch("serial_command_sender.gui.sys.frozen", True, create=True), patch(
                "serial_command_sender.gui.sys.executable", str(directory / "app.exe")
            ):
                self.assertIsNone(find_commands_file())
                header = directory / "Device_commands.h"
                header.write_text("// Device commands\n#define START 1\n")
                self.assertEqual(find_commands_file(), header)


if __name__ == "__main__":
    unittest.main()
