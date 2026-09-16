"""Header loading and incremental ACK decoding, independent of the GUI."""
import re
from pathlib import Path


def parse_groups(filepath):
    groups = {}
    current = None
    kind = "commands"
    source = Path(filepath).read_text(encoding="utf-8-sig")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    for line in source.splitlines():
        section = re.match(r"\s*//\s*(.*?)\s+(ack\s+)?commands?\s*$", line, re.I)
        if section:
            current = section[1].strip().title()
            kind = "acks" if section[2] else "commands"
            groups.setdefault(current, {"commands": [], "acks": []})
            continue
        if current and re.match(r"\s*#\s*define\b", line):
            definition = line.split("//", 1)[0].strip()
            match = re.fullmatch(
                r"#\s*define\s+(\w+)\s+\(?\s*(0[xX][\da-fA-F]+|\d+)[uUlL]*\s*\)?", definition
            )
            if not match:
                raise ValueError(f"Unsupported command definition: {definition}")
            name, literal = match.groups()
            if literal.lower().startswith("0x"):
                digits = literal[2:]
            else:
                if len(literal) > 1 and literal.startswith("0"):
                    raise ValueError(f"Use decimal without leading zeros or hex: {definition}")
                digits = f"{int(literal):X}"
            digits = digits.zfill(len(digits) + len(digits) % 2).upper()
            groups[current][kind].append((name, digits))
    if not groups:
        raise ValueError("No command groups found in the header.")
    return groups


class AckDecoder:
    MODES = ("Raw bytes", "HEX text", "DEC text")

    def __init__(self, groups, mode="Raw bytes"):
        self.mode = mode
        self.buffer = bytearray()
        self.codes = {}
        self.numbers = {}
        for group in groups.values():
            for name, digits in group["acks"]:
                self.codes.setdefault(bytes.fromhex(digits), []).append(name)
                self.numbers.setdefault(int(digits, 16), []).append(name)

    def reset(self):
        self.buffer.clear()

    def feed(self, data=b"", final=False):
        self.buffer.extend(data)
        messages = []
        if self.mode != "Raw bytes":
            while self.buffer:
                separator = re.search(rb"[\s,;\x00]+", self.buffer)
                if separator:
                    token = bytes(self.buffer[:separator.start()])
                    del self.buffer[:separator.end()]
                elif final or len(self.buffer) > 256:
                    token = bytes(self.buffer)
                    self.buffer.clear()
                else:
                    break
                if not token:
                    continue
                pattern = rb"(?:0[xX])?[0-9a-fA-F]+" if self.mode == "HEX text" else rb"[0-9]+"
                if re.fullmatch(pattern, token):
                    value = int(token, 16 if self.mode == "HEX text" else 10)
                    messages.append(" / ".join(self.numbers.get(value, [f"Unknown ACK: {value} (0x{value:X})"])))
                else:
                    messages.append(f"Invalid {self.mode}: {token!r}")
            return messages
        while self.buffer:
            pending = bytes(self.buffer)
            matches = [code for code in self.codes if pending.startswith(code)]
            # Wait for a split multi-byte code, including a longer overlapping code.
            if not final and any(code.startswith(pending) and len(code) > len(pending) for code in self.codes):
                break
            if matches:
                code = max(matches, key=len)
                messages.append(" / ".join(self.codes[code]))
                del self.buffer[:len(code)]
            else:
                value = self.buffer.pop(0)
                if value not in (0, 10, 13):
                    messages.append(f"Unknown ACK: 0x{value:02X} ({value})")
        return messages
