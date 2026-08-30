"""The burst as the time-base: interval-fraction change across ~44 frames.

Video moves in nearly every 1/30s interval; a dialog animation touches a few;
a still screen none. Per pixel, the fraction of consecutive-frame intervals
with a real change, measured at working width on the capture burst itself.
"""
import glob
import sys
import tempfile
import cv2
import numpy as np

sys.path.insert(0, ".")
import capture

CASES = [
    ("install", "G:/Video/Install Claude Code and-or the AI Memory Vault",
     "00:07:14", (2736, 1344, 3706, 2074)),
    ("works", "G:/Video/How Claude Code Actually Works",
     "00:07:29", (2669, 1142, 3763, 2074)),
    ("obsidian", "G:/Video/How To Set Up Claude Code With Obsidian",
     "00:02:09", None),
]

WORDS = {
    "install": [("fifine", (3429, 1911, 3494, 1980)),
                ("Hat", (3187, 1456, 3282, 1511)),
                ("Cancel", (1834, 1534, 2009, 1588)),
                ("dialog prose", (1496, 1022, 2343, 1070)),
                ("2026-07-22", (3451, 54, 3757, 100))],
    "works": [("Har", (3276, 1296, 3398, 1366))],
}

for name, folder, stamp, inset in CASES:
    vid = sorted(glob.glob(folder + "/*.mp4"))[0]
    with tempfile.TemporaryDirectory() as work:
        files = capture._ffmpeg_burst(vid, capture._to_seconds(stamp),
                                      capture.BURST_SECONDS, work)
        small = []
        native_w = None
        for f in files:
            b = cv2.imread(f)
            if b is None:
                continue
            native_w = b.shape[1]
            h = int(b.shape[0] * 1280 / b.shape[1])
            small.append(cv2.resize(b, (1280, h),
                                    interpolation=cv2.INTER_AREA)
                         .astype(np.int16))
        moved = np.zeros(small[0].shape[:2], np.int32)
        for a, b in zip(small, small[1:]):
            moved += (np.abs(a - b).max(axis=2) > 8).astype(np.int32)
        frac = moved / float(len(small) - 1)
        h, w = frac.shape
        s = 1280.0 / native_w
        print(f"\n=== {name} {stamp}: burst of {len(small)}, map {w}x{h} ===")
        for cut in (0.3, 0.5, 0.8):
            mask = (frac >= cut).astype(np.uint8)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            big = [(stats[i, 4], stats[i, 0], stats[i, 1],
                    stats[i, 0] + stats[i, 2], stats[i, 1] + stats[i, 3])
                   for i in range(1, n) if stats[i, 4] >= 0.001 * h * w]
            big.sort(reverse=True)
            print(f"  frac>={cut:.1f}: {float(mask.mean())*100:5.1f}% of "
                  f"frame, {len(big)} big blob(s)")
            for _, x0, y0, x1, y1 in big[:5]:
                print(f"      blob x{x0}-{x1} y{y0}-{y1}")
        if inset:
            ix0, iy0, ix1, iy1 = [int(v * s) for v in inset]
            inside = frac[iy0:iy1, ix0:ix1]
            outside = frac.copy()
            outside[iy0:iy1, ix0:ix1] = -1
            ov = outside[outside >= 0]
            print(f"  inset p50 {np.median(inside):.2f} "
                  f"p90 {np.percentile(inside, 90):.2f}   outside "
                  f"p50 {np.median(ov):.2f} p90 {np.percentile(ov, 90):.2f} "
                  f"p99 {np.percentile(ov, 99):.2f}")
        for label, (x0, y0, x1, y1) in WORDS.get(name, []):
            X0, Y0, X1, Y1 = [int(v * s) for v in (x0, y0, x1, y1)]
            patch = frac[Y0:Y1, X0:X1]
            if patch.size == 0:
                print(f"    word {label!r}: empty at working size")
                continue
            print(f"    word {label!r:14} frac p50 {np.median(patch):.2f} "
                  f"p90 {np.percentile(patch, 90):.2f}")
