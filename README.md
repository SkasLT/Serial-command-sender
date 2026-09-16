# Serial Command Sender

Send raw serial commands from a C header and decode incoming ACK values by name.

## Run the included Windows app

Copy these two files from `dist/` into the same folder on another Windows PC:

- [Serial Command Sender.exe](dist/Serial%20Command%20Sender.exe)
- [My_device_commands.h](dist/My_device_commands.h)

Double-click the executable. Python and a separate release download are not
required. These two files are intentionally kept in the repository for easy
copying. When changing the Python source, rebuild the executable and commit the
updated binary along with the source changes.

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

With no `--commands` argument, the Python application uses the single
`*_commands.h` in the current working directory, or the packaged example at
`src/serial_command_sender/data/My_device_commands.h` when none is present.
Multiple matching headers produce an error. Copy the example to your device
folder and customize that copy instead of editing files inside an installation.

The portable executable requires one `*_commands.h` beside the executable unless
`--commands` is supplied. It does not depend on the launch working directory.
The active header's path appears in the traffic display.

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
    My_device_commands.h      # Required alongside the executable
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
Decoded return message: "MIXER_STARTED"
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

Distribute these two files together (for example, in a ZIP):

```text
dist/
  Serial Command Sender.exe
  My_device_commands.h
```

The target PC does not need Python. It needs Windows compatible with the build
architecture and a driver for its USB serial adapter. The header remains editable;
restart the program after changing it. The previous root-level executable and
header have been preserved locally in `dist/legacy/`; new builds are in `dist/`.

PyInstaller's `--onefile` packages dependencies into one executable; `--windowed`
suppresses the console. See the [official PyInstaller usage documentation](https://pyinstaller.org/en/stable/usage.html).

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
