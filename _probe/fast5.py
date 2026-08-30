#!/usr/bin/env python3
"""The right instruments for weight and underline, measured on real rows.

Weight: stroke thickness by distance transform -- twice the mean distance
of ink pixels to the nearest background pixel, per row, normalised by row
height. The ink-share proxy failed: it fires on highlight badges.

Underline: a THIN band (<= 0.14 of row height) of ink just below the
baseline covering >= 0.7 of the text width -- and not running past the
text into the pane, which is what a table border does.
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")

import cv2
import numpy as np

import tree_reader

SETS = [
    ("memory", r"G:\Images\How I Gave My AI Unlimited Memory\Images\*_pane*.png", 6),
    ("movemem", r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\*_pane*.png", 6),
    ("funnel", r"G:\Images\The Sales Funnel That Built My _1M-Year Business\Images\*_pane*.png", 6),
    ("post", r"G:\Images\A Look Inside My Million Dollar AI Business\Images\00-00-30_pane0.png", 1),
]


def main():
    for label, pattern, cap in SETS:
        picked = [p for p in sorted(glob.glob(pattern))
                  if "_3x" not in p and "_tess" not in p][:cap]
        for pane in picked:
            img = cv2.imread(pane)
            if img is None:
                continue
            rows = [r for r in tree_reader.ocr_rows(pane)
                    if len(r["text"]) >= 3]
            if len(rows) < 3:
                continue
            sws = []
            per = []
            for r in rows:
                crop = img[max(0, r["y0"]):r["y1"],
                           max(0, r["x0"]):r["x1"]]
                if crop.size == 0:
                    per.append(None)
                    sws.append(0)
                    continue
                bg = np.median(crop.reshape(-1, 3), axis=0)
                ink = (np.abs(crop.astype(np.int16) - bg).max(axis=2)
                       > 60).astype(np.uint8)
                if ink.sum() < 40:
                    per.append(None)
                    sws.append(0)
                    continue
                dist = cv2.distanceTransform(ink, cv2.DIST_L2, 3)
                sw = 2.0 * float(dist[ink > 0].mean())
                rowh = r["y1"] - r["y0"]
                sws.append(sw)
                # underline: thin band under the baseline, text-width only
                band_h = max(2, int(0.30 * rowh))
                y2 = min(img.shape[0], r["y1"] + band_h)
                x0 = max(0, r["x0"])
                strip = img[r["y1"]:y2, x0:r["x1"]]
                under = ""
                if strip.size:
                    sink = (np.abs(strip.astype(np.int16) - bg).max(axis=2)
                            > 60)
                    for yy in range(sink.shape[0]):
                        line = sink[yy]
                        cover = float(line.mean())
                        if cover >= 0.7:
                            # thin? count contiguous rows of this coverage
                            thick = 1
                            z = yy + 1
                            while z < sink.shape[0] and sink[z].mean() >= 0.7:
                                thick += 1
                                z += 1
                            # a border runs past the text: look left/right
                            lx0 = max(0, x0 - 3 * rowh)
                            lx1 = min(img.shape[1], r["x1"] + 3 * rowh)
                            wide = img[r["y1"] + yy:r["y1"] + yy + 1,
                                       lx0:lx1]
                            wink = (np.abs(wide.astype(np.int16) - bg)
                                    .max(axis=2) > 60)
                            beyond = float(wink.mean())
                            under = (f"band@{yy} thick{thick} "
                                     f"beyond{beyond:.2f}")
                            break
                per.append((sw, rowh, under))
            good = [s for s in sws if s > 0]
            if not good:
                continue
            med = float(np.median(good))
            name = os.path.basename(pane)
            print(f"== {label}  {name}  ({len(rows)} rows, "
                  f"median stroke {med:.2f})")
            for r, p in zip(rows, per):
                if p is None:
                    continue
                sw, rowh, under = p
                rel = sw / med if med else 0
                mark = " <-- heavy?" if rel >= 1.3 else ""
                umark = f"  {under}" if under else ""
                print(f"   {r['text'][:34]:<34} sw{sw:>5.2f} rel{rel:>5.2f} "
                      f"h{rowh:>3}{mark}{umark}")
    print("\nfast5 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
