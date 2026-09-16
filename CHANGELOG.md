# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [1.3.0] - 2026-09-16

### Added
- Incoming ACK decoding with a separate display and raw, HEX text, and DEC text modes.
- Installable `src/serial_command_sender` package with `pyproject.toml` metadata.
- `serial-command-sender` and `python -m serial_command_sender` launch commands.
- `--commands` option, packaged example header, tests, and a Windows build script.

### Changed
- Moved GUI updates onto the main thread and improved serial connection handling.
- Centralized dependencies in `pyproject.toml`; removed `requirements.txt`.
- Moved generated executables and old release files out of the source tree.
- Expanded `.gitignore` for environments, package metadata, build products, and caches.

## [1.2.0] - 2025-11-05

### Changed
- Search and loading:
  - File search now looks in the script directory and subdirectories for *_commands.h to avoid dependence on the current working directory when launching the app.
- Command parsing & sending:
  - Header parser preserves the original hex strings from the header (e.g. "0601", "80").
  - When sending, hex strings are interpreted as sequences of bytes:
    - Multi-byte values (e.g. 0xAABB) are sent sequentially (0xAA then 0xBB).
    - Single-byte values (e.g. 0x80) are sent as a single byte.
  - End-character behavior (CR/LF/etc.) remains unchanged and is appended after the command bytes.

---

## [1.1.0] - 2025-04-27

### Added

- Recognition of both singular and plural group comments (e.g. `// Mixer command` and `// Mixer commands`)

## [1.0.0] - 2025-04-24

### Added

- Initial release of Serial Command Sender (.exe) version
- Supports grouped command parsing from *_commands.h files
- Command and ACK grouping based on comments
- Collapsible command menus with side-by-side ACK display
- Serial monitor with ASCII / HEX / DEC / HEX + ASCII display modes
- Auto-scroll and clear options in monitor
- Command search bar
- Header file + .exe coexistence requirement enforced
- README.md and LICENSE (MIT) included
