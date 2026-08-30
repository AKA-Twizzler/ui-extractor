import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import numpy as np, spot, machine
video = r"G:\Video\Move Memory Files Out of Claude Code Into Obsidian\Move Memory Files Out of Claude Code Into Obsidian (2160p_30fps_AV1-128kbit_AAC-English).mp4"
cache = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/scan.json")
samples = spot.scan(video, 10, cache, rescan=False)
print("samples", len(samples), "CELL", spot.CELL, "BOUND", spot.CELL_BOUND, "EVERY", spot.CELL_EVERY)
for run in spot.stretches(samples):
    if run["call"] != "screen":
        continue
    st = [s for s in samples if run["start"] <= s["t"] <= run["end"]]
    print("stretch", spot.hms(run["start"]), "-", spot.hms(run["end"]), "samples", len(st))
    if len(st) < 3:
        continue
    thumbs = [np.array(s["thumb"], np.float32) for s in st]
    h, w = thumbs[0].shape
    hc, wc = h // spot.CELL, w // spot.CELL
    steps = np.array([np.abs(a - b)[:hc * spot.CELL, :wc * spot.CELL].reshape(hc, spot.CELL, wc, spot.CELL).mean(axis=(1, 3)) for a, b in zip(thumbs, thumbs[1:])])
    moving = (steps > spot.CELL_BOUND).mean(axis=0) >= spot.CELL_EVERY
    print("   moving cells share %.2f of %d" % (moving.mean(), moving.size))
    for i, cells in enumerate(steps):
        over = cells > spot.CELL_BOUND
        quiet_hit = (cells[~moving] > spot.CELL_BOUND).any()
        print("   %s -> %s: cells over bound %.3f (quiet %.3f) %s" % (spot.hms(st[i]["t"]), spot.hms(st[i+1]["t"]), over.mean(), (cells[~moving] > spot.CELL_BOUND).mean() if (~moving).any() else 0, "TAKEN" if quiet_hit else ""))
