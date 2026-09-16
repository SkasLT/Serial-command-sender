import tempfile
import unittest
from pathlib import Path

from serial_command_sender.ack_decoder import AckDecoder, parse_groups


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.groups = {"Device": {"commands": [], "acks": [
            ("STARTED", "81"), ("STOPPED", "82"), ("READY", "0601")
        ]}}

    def test_raw_combined_and_split(self):
        decoder = AckDecoder(self.groups)
        self.assertEqual(decoder.feed(b"\x81\x82\r\n\x06"), ["STARTED", "STOPPED"])
        self.assertEqual(decoder.feed(b"\x01"), ["READY"])

    def test_unknown_and_partial(self):
        decoder = AckDecoder(self.groups)
        self.assertEqual(decoder.feed(b"\xff"), ["Unknown ACK: 0xFF (255)"])
        self.assertEqual(decoder.feed(b"\x06"), [])
        self.assertEqual(decoder.feed(final=True), ["Unknown ACK: 0x06 (6)"])

    def test_numeric_text(self):
        for mode, chunks in [("HEX text", [b"0x8", b"1 82;0601\r\n"]),
                             ("DEC text", [b"12", b"9,130 1537\r\n"])]:
            decoder = AckDecoder(self.groups, mode)
            self.assertEqual(decoder.feed(chunks[0]), [])
            self.assertEqual(decoder.feed(chunks[1]), ["STARTED", "STOPPED", "READY"])

    def test_text_idle_invalid_and_reset(self):
        decoder = AckDecoder(self.groups, "DEC text")
        self.assertEqual(decoder.feed(b"129"), [])
        self.assertEqual(decoder.feed(final=True), ["STARTED"])
        self.assertIn("Invalid", decoder.feed(b"abc\n")[0])
        decoder.feed(b"12")
        decoder.reset()
        self.assertEqual(decoder.feed(b"130\n"), ["STOPPED"])

    def test_overlapping_codes_and_aliases(self):
        self.groups["Device"]["acks"] += [("LONG", "8101"), ("ALIAS", "82")]
        decoder = AckDecoder(self.groups)
        self.assertEqual(decoder.feed(b"\x81"), [])
        self.assertEqual(decoder.feed(b"\x01\x82"), ["LONG", "STOPPED / ALIAS"])
        decoder.feed(b"\x81")
        self.assertEqual(decoder.feed(final=True), ["STARTED"])

    def test_header_literals_and_width(self):
        with tempfile.TemporaryDirectory() as folder:
            header = Path(folder) / "test_commands.h"
            header.write_text("// Device commands\n  #define START 0x0001\n"
                              "// Device ack commands\n #define STARTED (129U)\n"
                              "#define READY 0X0601 // comment\n", encoding="utf-8")
            groups = parse_groups(header)
            self.assertEqual(groups["Device"]["commands"], [("START", "0001")])
            self.assertEqual(groups["Device"]["acks"], [("STARTED", "81"), ("READY", "0601")])
            header.write_text("// Device commands\n#define BAD (1 << 7)\n")
            with self.assertRaises(ValueError):
                parse_groups(header)


if __name__ == "__main__":
    unittest.main()
