#!/usr/bin/env python3
"""Debug dump for the geometry calibration: per-row pixel reality of the icon band.

For each tesseract line in the strip, print:
  - the row text and y-band
  - the first-alpha-token x (the text anchor)
  - an ASCII map of the pixel band left of the text (columns 0..text_x),
    so guide lines, chevrons, and icons are visible before any threshold is set.

Run: .venv/bin/python debug_dump.py <strip.png>
"""
import sys
import numpy as np
import cv2

from ui_geometry import tesseract_tsv, group_lines, strip_furniture_by_gaps
import machine

BRIGHT = 100  # Obsidian icons are dim gray; text is bright


def ascii_band(img, y0, y1, x0, x1, cols=110):
    """Downsample the band to ~cols columns and print rows of chars."""
    band = img[max(0, y0):y1, max(0, x0):x1]
    if band.size == 0:
        return "(empty)"
    h, w = band.shape
    step = max(1, w // cols)
    lines = []
    # print every 6th pixel row to keep the map short
    for r in range(0, h, 6):
        row = []
        for c in range(0, w, step):
            v = int(band[r, c])
            row.append(" " if v < 60 else "." if v < 100 else ":" if v < 140 else "o" if v < 190 else "#")
        lines.append("".join(row))
    return "\n".join(lines)


def main():
    png = sys.argv[1]
    img = cv2.imread(png, cv2.IMREAD_GRAYSCALE)
    rows = tesseract_tsv(png)
    lines = group_lines(rows)
    lines = strip_furniture_by_gaps(lines)

    print(f"image {img.shape[1]}x{img.shape[0]}, {len(lines)} lines")
    print("=" * 100)
    for ln in lines:
        text_x = None
        for w in ln["words"]:
            t = w["text"]
            if t.isalpha() and len(t) >= 3 and float(w["conf"]) >= 40:
                text_x = int(w["left"])
                break
        if text_x is None:
            text_x = int(ln["x"])
        y0 = max(0, int(ln["y"]) - 4)
        y1 = min(img.shape[0], int(ln["bottom"]) + 4)
        band_x0 = max(0, text_x - 160)
        print(f"y={ln['y']:>4} text_x={text_x:>4} | {ln['text']}")
        print(ascii_band(img, y0, y1, band_x0, text_x + 2))
        print("-" * 100)


if __name__ == "__main__":
    main()