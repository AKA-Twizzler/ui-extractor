#!/usr/bin/env python3
"""Numeric icon-band profile: exact bright-run positions per row.

For each row: text, text_x, then every contiguous run of columns whose mean
brightness clears the floor, as (x0, x1, width, peak). Guide lines are
single-column runs; chevrons and icons are blobs. This is the raw pixel
reality the thresholds get calibrated against.
"""
import sys
import numpy as np
import cv2

from ui_geometry import tesseract_tsv, group_lines, strip_furniture_by_gaps
import machine

FLOOR = 60  # brightness floor for a run to count (0-255)


def runs_of(colmean):
    """Split the column profile into contiguous runs above FLOOR."""
    runs = []
    on = False
    start = 0
    for i, v in enumerate(colmean):
        if not on and v >= FLOOR:
            on, start = True, i
        elif on and v < FLOOR:
            on = False
            runs.append((start, i - 1))
    if on:
        runs.append((start, len(colmean) - 1))
    return runs


def main():
    png = sys.argv[1]
    img = machine.pixels(png, cv2.IMREAD_GRAYSCALE)
    lines = strip_furniture_by_gaps(group_lines(tesseract_tsv(png)))

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
        band = img[y0:y1, 0:text_x]
        if band.size == 0:
            print(f"y={ln['y']:>4} text_x={text_x:>4} | {ln['text']}  (no band)")
            continue
        colmean = band.mean(axis=0)
        # report only runs of 1+ columns; merge trivial noise under 2px wide
        runs = [(x0, x1, x1 - x0 + 1, int(colmean[x0:x1 + 1].max()))
                for x0, x1 in runs_of(colmean) if x1 - x0 + 1 >= 1]
        # compress: runs within 4px of each other that are both thin (guide
        # line fragments) stay separate; blobs stay whole
        desc = " ".join(f"[{x0}-{x1} w{w} pk{peak}]" for x0, x1, w, peak in runs)
        print(f"y={ln['y']:>4} text_x={text_x:>4} | {ln['text']}")
        print(f"    runs: {desc if desc else '(none)'}")


if __name__ == "__main__":
    main()