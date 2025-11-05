# Serial Command Sender

A standalone `.exe` application for sending commands over serial (COM) to embedded devices.
Supports grouped commands and ACK responses loaded dynamically from a C header file.

---

## 📦 Usage

### 1. Running the Application

Place your `.exe` file and a properly formatted header file (e.g. `My_device_commands.h`) in the **same folder**.

> ⚠️ The app will only work if the header file and `.exe` are located in the **same directory**.

Double-click the `.exe` or run it.

---

### 2. Required Header File Format

The header file must:

- Be named with the pattern: `*_commands.h` (e.g. `Display_controller_commands.h`)
- Use **C-style `#define` macros**
- Use **comments** to define command groups and acknowledgment groups:
  - `// XYZ commands` → command group
  - `// XYZ ack commands` → ack group
- Use **two blank lines** between command sections

---

### ✅ Example: Correctly Formatted `My_device_commands.h`

```c
/*
 * Example correctly formatted C header file for command set.
 */

#ifndef MY_DEVICE_COMMANDS_H_
#define MY_DEVICE_COMMANDS_H_

// Mixer commands
#define MIXER_START 0x01
#define MIXER_STOP  0x02
// Mixer ack commands
#define MIXER_STARTED 0x81
#define MIXER_STOPPED 0x82


// Display commands
#define DISPLAY_INIT  0x10
#define DISPLAY_CLEAR 0x11
// Display ack commands
#define DISPLAY_READY 0x90
#define DISPLAY_DONE  0x91

// Multy byte commands
#define MULTY_BYTE_CMD1 0x0001
#define MULTY_BYTE_CMD2 0x0002

#endif     // MY_DEVICE_COMMANDS_H_
```

---

## 📁 Folder Structure

Your working directory should follow this layout:

```
📂 Project Folder
├── Serial Command Sender.exe          # Main executable
├── My_device_commands.h              # Active header file (must match *_commands.h)
└── 📂 src/
    ├── Serial_gui.py                    # Python source code (optional, for reference)
    └── My_device_commands.h          # Header backup or alternate command set
```

> 📝 Only the `.h` file in the root folder will be loaded by the `.exe`. Files inside `source/` are for development purposes only.

---

## 🖥️ Application Features

- Serial port & baud rate selection
- End-of-line character configuration
- Collapsible menus per board/group
- Commands & ACKs shown side-by-side
- Live command filtering via search bar
- Real-time serial monitor with:
  - ASCII
  - HEX
  - DEC
  - HEX + ASCII formats

---

## 📄 Tips

- Command values are sent as raw bytes with optional end characters
- ACK values are **not sent**, only displayed for reference
- You can use multiple boards/groups as long as each is separated by **two blank lines** in the header file

---

## ⚠️ Disclaimer

This source code was generated with the help of ChatGPT and assembled quickly for testing and internal development purposes.
It is not a professionally developed or security-reviewed application. Use at your own discretion in controlled environments.

---
