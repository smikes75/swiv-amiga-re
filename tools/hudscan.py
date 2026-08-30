#!/usr/bin/env python3
"""Extract and verify SWIV's native one-bit HUD font and initial mask.

The input may be either the custom-format SWIVFIX.ADF or an already
unpacked AMPROG.OBJ:

    python3 tools/hudscan.py SWIVFIX.ADF
    python3 tools/hudscan.py build/files/001_AMPROG.OBJ

Nothing is written.  A non-zero exit status means that the embedded font or
the rendered initial HUD differs from the audited AMPROG.OBJ contract.
"""

import argparse
import hashlib
import os
import sys


FONT_LOOKUP = 0xD384
FIRST_CHAR = 32
LAST_CHAR = 94
GLYPH_BYTES = 16
FONT_START = FONT_LOOKUP + FIRST_CHAR * GLYPH_BYTES
FONT_END = FONT_LOOKUP + (LAST_CHAR + 1) * GLYPH_BYTES

HUD_WIDTH = 352
HUD_HEIGHT = 8
HUD_STRIDE = HUD_WIDTH // 8
GLYPH_ROWS = 7

LEFT_TEXT = "HELI 4[ 2* 0000000"
LEFT_X = 8
RIGHT_TEXT = "PRESS FIRE"
RIGHT_ANCHOR = 312

EXPECTED_FONT_SHA256 = (
    "f9a3f735b03252759ff3d0eeb7c71cadb84eadce6fb0b077905f9c05842934db"
)
EXPECTED_MASK_SHA256 = (
    "083735374ea183f35350e6bbd4cb97e6bb8202d81ae7f51621764093154cd894"
)
EXPECTED_SET_BITS = 638


class HudError(Exception):
    """An input cannot satisfy the native HUD contract."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_amprog(path):
    """Return (AMPROG bytes, source description) from an ADF or raw object."""
    with open(path, "rb") as src:
        data = src.read()

    if len(data) == 901120 and data[:4] == b"DOS\x00":
        # tools/ is already sys.path[0] for normal script invocation.  Keep
        # the insertion explicit for callers which import and invoke main().
        tools_dir = os.path.dirname(os.path.abspath(__file__))
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        from extract import StreamC, catalog

        entries = catalog(data)
        matches = [(i, row) for i, row in enumerate(entries)
                   if row[0].upper() == "AMPROG.OBJ"]
        if len(matches) != 1:
            raise HudError("ADF contains %d AMPROG.OBJ entries" % len(matches))
        index, (name, offset, _stored, unpacked_size) = matches[0]
        program = StreamC(data, offset + 4).unpack(unpacked_size)
        description = "%s -> file %d %s" % (path, index, name)
        return program, description

    return data, "%s (raw AMPROG.OBJ)" % path


def extract_font(program):
    if len(program) < FONT_END:
        raise HudError(
            "AMPROG.OBJ is too short for font end 0x%X (%d bytes)"
            % (FONT_END, len(program))
        )
    blob = program[FONT_START:FONT_END]
    glyphs = {}
    for code in range(FIRST_CHAR, LAST_CHAR + 1):
        offset = FONT_LOOKUP + code * GLYPH_BYTES
        record = program[offset:offset + GLYPH_BYTES]
        width = int.from_bytes(record[:2], "big")
        if not 0 <= width <= 16:
            raise HudError("invalid width %d for ASCII %d" % (width, code))
        rows = tuple(
            int.from_bytes(record[2 + row * 2:4 + row * 2], "big")
            for row in range(GLYPH_ROWS)
        )
        glyphs[chr(code)] = (width, rows)
    return blob, glyphs


def native_char(char):
    """The original renderer folds lower-case input to its upper-case font."""
    if "a" <= char <= "z":
        char = chr(ord(char) - (ord("a") - ord("A")))
    if not FIRST_CHAR <= ord(char) <= LAST_CHAR:
        raise HudError("character %r is outside drawable ASCII 32..94" % char)
    return char


def text_width(text, glyphs):
    # The formatter includes the one-pixel advance after the final glyph.
    return sum(glyphs[native_char(char)][0] + 1 for char in text)


def draw_text(mask, text, x, glyphs):
    width = text_width(text, glyphs)
    if x < 0 or x + width > HUD_WIDTH:
        raise HudError("text %r at x=%d exceeds the %d-pixel HUD" %
                       (text, x, HUD_WIDTH))

    pen = x
    for char in text:
        glyph_width, rows = glyphs[native_char(char)]
        for y, row_bits in enumerate(rows):
            for local_x in range(glyph_width):
                if row_bits & (1 << (glyph_width - 1 - local_x)):
                    pixel_x = pen + local_x
                    byte = y * HUD_STRIDE + pixel_x // 8
                    mask[byte] |= 1 << (7 - pixel_x % 8)
        pen += glyph_width + 1
    return pen


def render_initial_mask(glyphs):
    mask = bytearray(HUD_STRIDE * HUD_HEIGHT)
    left_width = text_width(LEFT_TEXT, glyphs)
    right_width = text_width(RIGHT_TEXT, glyphs)
    right_x = RIGHT_ANCHOR - right_width
    draw_text(mask, LEFT_TEXT, LEFT_X, glyphs)
    draw_text(mask, RIGHT_TEXT, right_x, glyphs)
    return bytes(mask), left_width, right_width, right_x


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", nargs="?", default="SWIVFIX.ADF",
        help="SWIVFIX.ADF or unpacked AMPROG.OBJ (default: SWIVFIX.ADF)",
    )
    args = parser.parse_args(argv)

    try:
        program, source = load_amprog(args.source)
        font_blob, glyphs = extract_font(program)
        mask, left_width, right_width, right_x = render_initial_mask(glyphs)
    except (HudError, OSError, IndexError) as exc:
        parser.exit(1, "hudscan: %s\n" % exc)

    font_hash = sha256(font_blob)
    mask_hash = sha256(mask)
    set_bits = sum(bin(byte).count("1") for byte in mask)
    checks = (
        ("font SHA-256", font_hash == EXPECTED_FONT_SHA256),
        ("mask SHA-256", mask_hash == EXPECTED_MASK_SHA256),
        ("mask set bits", set_bits == EXPECTED_SET_BITS),
    )

    print("source: %s" % source)
    print("AMPROG.OBJ: %d bytes" % len(program))
    print("font: lookup base 0x%04X, ASCII %d..%d, bytes 0x%04X..0x%04X"
          % (FONT_LOOKUP, FIRST_CHAR, LAST_CHAR, FONT_START, FONT_END - 1))
    print("font SHA-256: %s  %s" %
          (font_hash, "OK" if checks[0][1] else "FAIL"))
    print("left:  x=%d, width=%d, %r" % (LEFT_X, left_width, LEFT_TEXT))
    print("right: anchor=%d, x=%d, width=%d, %r" %
          (RIGHT_ANCHOR, right_x, right_width, RIGHT_TEXT))
    print("mask: %dx%d, stride=%d, %d bytes, %d set bits  %s" %
          (HUD_WIDTH, HUD_HEIGHT, HUD_STRIDE, len(mask), set_bits,
           "OK" if checks[2][1] else "FAIL"))
    print("mask SHA-256: %s  %s" %
          (mask_hash, "OK" if checks[1][1] else "FAIL"))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print("contract: FAIL (%s)" % ", ".join(failed))
        return 1
    print("contract: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
