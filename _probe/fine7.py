"""The whole video as the time-base, from spot's own scan cache.

Per thumb pixel, the fraction of consecutive 10s samples that changed. A
webcam inset differs at nearly every step for hours; any screen region has
long quiet spells. If the gap is real, the camera zone comes free with every
scanned video.
"""
import json
import sys
import numpy as np
import cv2

CASES = [
    ("install", "G:/Images/Install Claude Code and-or the AI Memory Vault",
     (2736, 1344, 3706, 2074), 3840),
    ("works", "G:/Images/How Claude Code Actually Works",
     (2669, 1142, 3763, 2074), 3840),
    ("obsidian", "G:/Images/How To Set Up Claude Code With Obsidian",
     None, 3840),
    ("stjude", "G:/Images/Jarvis and Jaredrhod Raise Money for St. Jude's "
     "Children's Hospital - Live Replay 8-1-26", None, 1920),
    ("july6", "G:/Images/Live Replay - July 6, 2026; AI marketing, Jarvis "
     "builds, and AI automation", None, 1920),
]

for name, folder, inset, native_w in CASES:
    try:
        d = json.load(open(folder + "/scan.json"))
    except OSError:
        print(f"{name}: no scan.json")
        continue
    thumbs = [np.array(s["thumb"], np.int16) for s in d["samples"]]
    print(f"\n=== {name}: {len(thumbs)} thumbs of {thumbs[0].shape} ===")
    moved = np.zeros(thumbs[0].shape, np.int32)
    for a, b in zip(thumbs, thumbs[1:]):
        moved += (np.abs(a - b) > 8).astype(np.int32)
    frac = moved / float(len(thumbs) - 1)
    h, w = frac.shape
    print(f"  frame frac p50 {np.median(frac):.2f} "
          f"p90 {np.percentile(frac, 90):.2f}")
    for cut in (0.5, 0.7, 0.85):
        mask = (frac >= cut).astype(np.uint8)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        big = [(stats[i, 4], stats[i, 0], stats[i, 1],
                stats[i, 0] + stats[i, 2], stats[i, 1] + stats[i, 3])
               for i in range(1, n) if stats[i, 4] >= 0.002 * h * w]
        big.sort(reverse=True)
        print(f"  frac>={cut:.2f}: {float(mask.mean())*100:5.1f}% of frame, "
              f"{len(big)} big blob(s)")
        for _, x0, y0, x1, y1 in big[:5]:
            print(f"      blob x{x0}-{x1} y{y0}-{y1}  "
                  f"(native x{int(x0*native_w/w)}-{int(x1*native_w/w)} "
                  f"y{int(y0*native_w/w)}-{int(y1*native_w/w)})")
    if inset:
        s = w / float(native_w)
        ix0, iy0, ix1, iy1 = [max(0, int(v * s)) for v in inset]
        inside = frac[iy0:iy1, ix0:ix1]
        outside = frac.copy()
        outside[iy0:iy1, ix0:ix1] = -1
        ov = outside[outside >= 0]
        print(f"  inset p10 {np.percentile(inside, 10):.2f} "
              f"p50 {np.median(inside):.2f}   outside "
              f"p50 {np.median(ov):.2f} p90 {np.percentile(ov, 90):.2f} "
              f"p99 {np.percentile(ov, 99):.2f}")
