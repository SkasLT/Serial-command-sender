# Serial Command Sender

Send raw serial commands from a C header and decode incoming ACK values by name.

## Run the included Windows app

Copy [Serial Command Sender.exe](dist/Serial%20Command%20Sender.exe) from `dist/`
to another Windows PC and double-click it. Python is not required, and no header
needs to be beside the executable.

Click **Load Command File** and select your device's `.h` file from any folder.
The full path appears below the button. An optional
[example header](dist/My_device_commands.h) is included in the repository.

When changing the Python source, rebuild the executable and commit the updated
binary along with the source changes.

## Development setup

Requires Python 3.10 or newer with Tk support. On Windows, use the standard Python
installer with Tcl/Tk enabled. From the project directory in PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m serial_command_sender
```

The installed GUI command is `.venv/Scripts/serial-command-sender.exe` on Windows
(or `serial-command-sender` with the environment activated). Do not run `gui.py`
directly: its imports belong to the installed package.

Runtime dependencies and development tools are declared in `pyproject.toml`.
For a normal installation without build tools, use `python -m pip install .`.

## Command headers

```powershell
.venv/Scripts/python -m serial_command_sender --commands "C:/devices/My_device_commands.h"
```

Use **Load Command File** to select or reload any `.h` file; it does not need
to be named `*_commands.h`. The label below the button always shows the active
file's full path and is not erased by **Clear Output**.

The `--commands` argument still loads a header at startup. Otherwise, a single
`*_commands.h` beside the executable (or in the working directory for Python)
is loaded automatically for convenience. If none or multiple are found, the app
opens with no command file loaded so you can choose one. The bundled example for
source installations is at `src/serial_command_sender/data/My_device_commands.h`.

Canceling the picker or selecting an invalid header preserves the current command
set. A successful load disconnects any active serial session, resets the search
and partial decoder input, and clears the decoded display. Reconnect to resume
communication. Traffic history remains visible. After editing a header, use the
button to reload it; no restart is needed. Selections are not saved across launches.

## Project layout

```text
Serial-command-sender/
  pyproject.toml               # Build system, metadata, dependencies, entry point
  MANIFEST.in                 # Extra files included in source distributions
  README.md
  CHANGELOG.md
  LICENSE
  .gitignore
  src/
    serial_command_sender/
      __init__.py
      __main__.py
      gui.py
      ack_decoder.py
      data/
        __init__.py
        app.ico               # Executable and Windows window/taskbar icon
        My_device_commands.h
  scripts/
    build_exe.py
    run_app.py                # PyInstaller entry point
  tests/
    test_ack_decoder.py
    test_serial_gui.py
    test_packaging.py
  build/                      # Generated; ignored by Git
  dist/
    Serial Command Sender.exe # Included for easy copying
    My_device_commands.h      # Optional example command header
    legacy/                   # Local backups; ignored by Git
```

Other generated files in `dist/`, including wheels and source archives, are ignored.

This follows the [PyPA packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
and its [src layout guidance](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
There is no single mandatory Python directory specification; `pyproject.toml`
provides the standardized metadata and build interface.

## Receive decoding

The small display below the traffic monitor shows, for example:

```text
[14:05:09] Decoded return message: "MIXER_STARTED"
```

Choose **Receive encoding** to match the device's wire protocol:

| Encoding | Example incoming data | Decoded name |
| --- | --- | --- |
| Raw bytes (default) | One byte `0x81` (decimal 129) | `MIXER_STARTED` |
| HEX text | ASCII `81` or `0x81` | `MIXER_STARTED` |
| DEC text | ASCII `129` | `MIXER_STARTED` |

**Display Format** only changes how traffic is shown. It does not change decoding
or the bytes sent. **End Char** only controls the terminator appended to commands.
**Clear Output** clears both displays and pending decoder input.

Every traffic and decoded-message entry starts with a local 24-hour timestamp
in `[HH:MM:SS]` format, for example `[14:05:09] Sent: 01 0D`.
Receive timestamps are captured when the application reads the bytes, and the
matching decoded messages use that same time. A reply assembled from multiple
reads uses the time of the read that completes it; idle-gap decoding retains the
last read's timestamp. These are PC timestamps, not device-generated timestamps.

Use the mouse wheel over the traffic display, decoded-message display, or command
list to scroll that panel, including when hovering over command labels or buttons.
Disable **Auto Scroll** to keep reading older output while new traffic arrives.

Numeric text uses one complete ACK value per token; separate values with spaces,
commas, semicolons, CR, LF, or NUL. For a multi-byte ACK `0x0601`, send text `0601`
in HEX text mode or `1537` in DEC text mode, not separate byte tokens.

Raw decoding uses the header's byte width and big-endian order, preserving leading
zeros: `0x0001` means bytes `00 01`. It handles combined and split reads. Known
codes take priority; unmatched CR, LF, and NUL are ignored as separators. Other
unknown bytes are shown with both their hex and decimal values. Duplicate values
show every matching name separated by `/`.

The header does not define packet framing. The decoder uses longest matching ACK
codes and waits up to a 300 ms idle gap for incomplete or ambiguous input. Numeric
text without a delimiter is also completed after that gap. Avoid codes that are
prefixes of other codes if your device sends adjacent ACKs without framing.
This is an ACK code monitor, not a parser for arbitrary payload packets: payload
bytes equal to ACK values will also be decoded. Devices with packet lengths,
checksums, little-endian codes, or longer inter-byte gaps need protocol-specific
handling.

## Header format

```c
// Mixer commands
#define MIXER_START 0x01
#define MIXER_STOP  0x02
// Mixer ack commands
#define MIXER_STARTED 0x81
#define MIXER_STOPPED 130

// Display commands
#define DISPLAY_INIT 0x0001
// Display ack commands
#define DISPLAY_READY 0x0601
```

Use `// <group> commands` and `// <group> ack commands` section headings.
Blank lines are optional. Values may be hex or decimal integer literals, with
optional parentheses and C integer suffixes. Decimal values use the minimum byte
width; use hex with leading zeros to specify a wider command. C expressions,
macro aliases, octal literals, and conditional preprocessing are not supported.
ACK names are taken only from ACK sections. ACKs are displayed but never sent by
the command buttons.

## Build a portable Windows executable

Run these commands in PowerShell from the project directory on Windows:

```powershell
.venv/Scripts/python scripts/build_exe.py
```

The script uses the current environment, resolves paths from the project root,
and preserves an existing customized header in `dist/` when rebuilding.

The executable can be distributed alone, or with the optional example header:

```text
dist/
  Serial Command Sender.exe
  My_device_commands.h
```

The target PC does not need Python. It needs Windows compatible with the build
architecture and a driver for its USB serial adapter. The header remains editable;
reload it with **Load Command File** after changing it. The previous root-level executable and
header have been preserved locally in `dist/legacy/`; new builds are in `dist/`.

PyInstaller's `--onefile` packages dependencies into one executable; `--windowed`
suppresses the console. See the [official PyInstaller usage documentation](https://pyinstaller.org/en/stable/usage.html).

## Custom Windows icon

The Windows icon is stored at `src/serial_command_sender/data/app.ico`. To change
it, replace that file with a multi-resolution Windows `.ico` and run
`.venv/Scripts/python scripts/build_exe.py`. The build embeds it in the executable
and bundles it for the running window; no separate icon file is needed beside the
`.exe`. Windows may cache a pinned shortcut's previous icon; unpin and re-pin the
rebuilt application if necessary.

## Build Python distributions

```powershell
.venv/Scripts/python -m build
```

This creates a wheel and a source archive in `dist/`, including the example
header and license. These are Python packages, separate from the portable Windows
executable. No publishing step is performed.

## Verification

```powershell
.venv/Scripts/python -m unittest discover -s tests -v
```

Tests cover header values and byte widths, raw and text decoding, fragmented and
combined replies, ambiguous codes, invalid data, and a GUI serial loopback test
including clear, repeated connect, disconnect, and stale-session handling.
The loopback test requires Tk but does not require serial hardware.
