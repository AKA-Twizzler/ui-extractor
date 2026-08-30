"""Sustained-motion zones: can they find the webcam inset and nothing else?

Sample a handful of frames across a screen's own stretch. Per pixel, count in
how many consecutive intervals it changed. Video changes in (almost) every
interval; typed text changes once; compression noise not at all. The zones
are the union boxes of the big moving blobs -- the mic inside the inset is
rigid and still, so the box has to swallow it.

Truth to hit:
  install 00:07:14  inset (2736,1344)-(3706,2074), rest screen
  works   00:07:29  inset (2669,1142)-(3763,2074), rest screen (terminal was
                    streaming output during the stretch -- must NOT be a zone)
  obsidian 00:02:09 no zone at all
  stjude  02:12:59  most of the frame one zone (it is a room)
"""
import glob
import os
import sys
import cv2
import numpy as np

sys.path.insert(0, ".")
import overlay
import screenness

CASES = [
    ("install", "G:/Video/Install Claude Code and-or the AI Memory Vault",
     434, (2736, 1344, 3706, 2074)),
    ("works", "G:/Video/How Claude Code Actually Works",
     449, (2669, 1142, 3763, 2074)),
    ("obsidian", "G:/Video/How To Set Up Claude Code With Obsidian",
     129, None),
    ("stjude", "G:/Video/Jarvis and Jaredrhod Raise Money for St. Jude's "
     "Children's Hospital - Live Replay 8-1-26", 7979, None),
]


def zones(paths, work_width=1280):
    shots = []
    for p in paths:
        b = cv2.imread(p)
        if b is None:
            continue
        h = int(b.shape[0] * work_width / b.shape[1])
        shots.append(cv2.resize(b, (work_width, h),
                                interpolation=cv2.INTER_AREA)
                     .astype(np.int16))
    if len(shots) < 3 or len({s.shape for s in shots}) != 1:
        return None, []
    moved = np.zeros(shots[0].shape[:2], np.int32)
    for a, b in zip(shots, shots[1:]):
        moved += (np.abs(a - b).max(axis=2) > 8).astype(np.int32)
    frac = moved / float(len(shots) - 1)
    return frac, shots


for name, folder, secs, inset in CASES:
    vids = sorted(glob.glob(folder + "/*.mp4"))
    if not vids:
        print(f"{name}: no video")
        continue
    wd = f"G:/Images/_probe/inset_{name}"
    paths = overlay.frames_across(vids[0], secs, span=24, looks=6, workdir=wd)
    frac, shots = zones(paths)
    if frac is None:
        print(f"{name}: not enough frames")
        continue
    h, w = frac.shape
    print(f"\n=== {name} at {secs}s: {len(paths)} looks, map {w}x{h} ===")
    for cut in (0.5, 0.8, 1.0):
        mask = (frac >= cut).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        big = [(stats[i, 4], stats[i, 0], stats[i, 1],
                stats[i, 0] + stats[i, 2], stats[i, 1] + stats[i, 3])
               for i in range(1, n) if stats[i, 4] >= 0.001 * h * w]
        big.sort(reverse=True)
        boxes = [b[1:] for b in big[:6]]
        share = float(mask.mean())
        print(f"  frac>={cut:.1f}: {share*100:5.1f}% of frame, "
              f"{len(big)} big blob(s)")
        for x0, y0, x1, y1 in boxes:
            print(f"      blob x{x0}-{x1} y{y0}-{y1}")
    if inset:
        s = w / cv2.imread(paths[0]).shape[1] if paths else 1
        ix0, iy0, ix1, iy1 = [int(v * w / 3840) for v in inset]
        inside = frac[iy0:iy1, ix0:ix1]
        outside = frac.copy()
        outside[iy0:iy1, ix0:ix1] = -1
        out_vals = outside[outside >= 0]
        print(f"  inset frac p50 {np.median(inside):.2f} "
              f"p90 {np.percentile(inside, 90):.2f}   "
              f"outside p50 {np.median(out_vals):.2f} "
              f"p90 {np.percentile(out_vals, 90):.2f} "
              f"p99 {np.percentile(out_vals, 99):.2f}")
