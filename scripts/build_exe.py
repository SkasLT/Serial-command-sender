"""Build the portable Windows application from any working directory."""
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    if sys.platform != "win32":
        raise SystemExit("Build the Windows executable on Windows.")
    root = Path(__file__).resolve().parents[1]
    icon = root / "src" / "serial_command_sender" / "data" / "app.ico"
    if not icon.is_file():
        raise SystemExit(f"Application icon not found: {icon}")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--collect-all", "ttkbootstrap", "--name", "Serial Command Sender",
        "--icon", str(icon),
        "--add-data", f"{icon}:serial_command_sender/data",
        "--paths", str(root / "src"), "--specpath", str(root / "build"),
        "--workpath", str(root / "build" / "pyinstaller"),
        "--distpath", str(root / "dist"), str(root / "scripts" / "run_app.py"),
    ], cwd=root, check=True)
    # Preserve a user's customized header when rebuilding.
    destination = root / "dist" / "My_device_commands.h"
    if not destination.exists():
        shutil.copy2(root / "src" / "serial_command_sender" / "data" / destination.name,
                     destination)
    print(f"Portable application: {root / 'dist'}")


if __name__ == "__main__":
    main()
