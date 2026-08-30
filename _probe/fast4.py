#!/usr/bin/env python3
"""What formatting is measurable on stored panes: per-row ink colour,
stroke weight, underline evidence. Measurement only -- no claims yet.

For each OCR row of each sampled pane:
  hue     dominant ink colour bucket (plain when unsaturated)
  sat     its saturation (0-255)
  wt      row ink-share over the pane's median row ink-share (bold > 1?)
  under   fraction of text width covered by ink in the strip just below
          the baseline (underline > 0.6?)
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
    ("obsidian", r"G:\Images\How To Set Up Claude Code With Obsidian\Images\00-00-40_pane*.png", 4),
    ("post", r"G:\Images\A Look Inside My Million Dollar AI Business\Images\00-00-30_pane*.png", 2),
    ("works", r"G:\Images\How Claude Code Actually Works\Images\00-00-20_pane*.png", 4),
    ("qna-chat", r"G:\Images\Live Q&A Answering Questions About AI Automation\Images\00-02-00_pane6.png", 1),
]

HUES = [(10, "red"), (22, "orange"), (33, "yellow"), (78, "green"),
        (100, "cyan"), (128, "blue"), (155, "purple"), (175, "pink"),
        (181, "red")]


def hue_name(h):
    for top, name in HUES:
        if h <= top:
            return name
    return "red"


def main():
    for label, pattern, cap in SETS:
        for pane in sorted(glob.glob(pattern))[:cap]:
            if "_3x" in pane or "_tess" in pane:
                continue
            img = cv2.imread(pane)
            if img is None:
                continue
            rows = [r for r in tree_reader.ocr_rows(pane)
                    if len(r["text"]) >= 3]
            if not rows:
                continue
            shares = []
            per = []
            for r in rows:
                crop = img[max(0, r["y0"]):r["y1"],
                           max(0, r["x0"]):r["x1"]]
                if crop.size == 0:
                    per.append(None)
                    shares.append(0)
                    continue
                bg = np.median(crop.reshape(-1, 3), axis=0)
                dist = np.abs(crop.astype(np.int16) - bg).max(axis=2)
                ink = dist > 60
                share = float(ink.mean())
                shares.append(share)
                if ink.sum() < 30:
                    per.append(None)
                    continue
                dom = np.median(crop[ink].reshape(-1, 3), axis=0) \
                    .astype(np.uint8).reshape(1, 1, 3)
                hsv = cv2.cvtColor(dom, cv2.COLOR_BGR2HSV)[0, 0]
                h = r["y1"] - r["y0"]
                strip = img[r["y1"]:min(img.shape[0],
                                        r["y1"] + max(2, int(0.35 * h))),
                            max(0, r["x0"]):r["x1"]]
                under = 0.0
                if strip.size:
                    sdist = np.abs(strip.astype(np.int16) - bg).max(axis=2)
                    cols = (sdist > 60).any(axis=0)
                    under = float(cols.mean())
                per.append((int(hsv[0]), int(hsv[1]), share, under))
            med = float(np.median([s for s in shares if s > 0]) or 1)
            print(f"== {label}  {os.path.basename(pane)}  "
                  f"({len(rows)} rows, median ink share {med:.3f})")
            for r, p in zip(rows, per):
                if p is None:
                    continue
                h, s, share, under = p
                hue = hue_name(h) if s >= 40 else "plain"
                wt = share / med if med else 0
                mark = ""
                if hue != "plain":
                    mark += f" <-- {hue}"
                if under >= 0.6:
                    mark += " <-- underlined?"
                if wt >= 1.5:
                    mark += " <-- heavy?"
                print(f"   {r['text'][:36]:<36} {hue:>7} sat{s:>4} "
                      f"wt{wt:>5.2f} under{under:>5.2f}{mark}")
    print("\nfast4 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
