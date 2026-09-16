"""PyInstaller entry point; normal users should use the installed entry point."""
from serial_command_sender.gui import main

if __name__ == "__main__":
    raise SystemExit(main())
