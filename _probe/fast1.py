#!/usr/bin/env python3
"""Where does a stream moment's time actually go, and how noisy are
consecutive sharpest-mode captures at full resolution.

Part 1: three consecutive moments of the Live Q&A video, every pipeline
phase timed with the real functions on the real frames.
Part 2: consecutive already-captured full frames (10s apart, same scene),
diffed in 100px tiles -- the still tiles' noise ceiling against the moving
tiles, for whether an "unchanged" claim is possible between sharpest-mode
captures.
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")

import cv2
import numpy as np

import capture
import overlay
import panes
import pipeline
import screenness

VIDEO = (r"G:\Video\Live Q&A Answering Questions About AI Automation"
         r"\Live Q&A Answering Questions About AI Automation "
         r"(1080p_30fps_H264-128kbit_AAC).mp4")
DONE = r"G:\Images\Live Q&A Answering Questions About AI Automation\Images"
WORK = r"G:\AI\Ethereal\ui-extractor\_probe\fast1_work"
os.makedirs(WORK, exist_ok=True)


def main():
    from rapidocr_onnxruntime import RapidOCR
    t0 = time.perf_counter()
    engine = RapidOCR()
    print(f"engine init: {time.perf_counter() - t0:.1f}s\n")

    for ts in ("00:01:40", "00:01:50", "00:02:00"):
        secs = int(ts[0:2]) * 3600 + int(ts[3:5]) * 60 + int(ts[6:8])
        T = {}

        def tick(name, fn, *a, **k):
            t = time.perf_counter()
            r = fn(*a, **k)
            T[name] = time.perf_counter() - t
            return r

        path, how = tick("capture burst", capture.capture_moment,
                         VIDEO, ts, WORK)
        img = cv2.imread(path)
        regions = tick("screenness", screenness.ui_regions, img, engine) or []
        wins = tick("windows", overlay.windows, img) or []
        tick("read_overlays", overlay.read_overlays, path, engine)
        looks = tick("frames_across 4/600s", overlay.frames_across,
                     VIDEO, secs, workdir=os.path.join(WORK, "_looks"))
        tick("standing_text", overlay.standing_text, looks, engine=engine)
        zlooks = tick("frames_across 6/24s", overlay.frames_across,
                      VIDEO, secs, span=overlay.ZONE_SPAN,
                      looks=overlay.ZONE_LOOKS,
                      workdir=os.path.join(WORK, "_zones"))
        tick("moving_zones", overlay.moving_zones, zlooks)
        boxes = tick("frame_regions", panes.frame_regions,
                     img, engine=engine) or []
        for pi, box in enumerate(boxes):
            pp = os.path.join(WORK, f"{ts.replace(':', '-')}_p{pi}.png")
            crop = panes.write_box(img, box, pp)
            if crop is None:
                continue
            rec = tick(f"say_pane {pi} "
                       f"({box[2]-box[0]}x{box[3]-box[1]})",
                       pipeline.say_pane, pp, pi, engine, (), None)
            if rec:
                T[f"say_pane {pi} ({box[2]-box[0]}x{box[3]-box[1]})"] = \
                    T.pop(f"say_pane {pi} ({box[2]-box[0]}x{box[3]-box[1]})")
                print(f"      pane {pi}: {rec['kind']}")
        for wi, win in enumerate(wins):
            tick(f"top_text w{wi}", pipeline.top_text, img, win, engine,
                 WORK, ts.replace(":", "-"))
        total = sum(T.values())
        print(f"--- {ts}  ({how}; {len(regions)} regions, {len(wins)} "
              f"windows, {len(boxes)} panes)  total {total:.1f}s")
        for name, dt in sorted(T.items(), key=lambda p: -p[1]):
            print(f"   {dt:7.1f}s  {name}")
        print()

    print("=== tile noise, consecutive finished captures (10s apart) ===")
    pairs = [("00-01-40", "00-01-50"), ("00-01-50", "00-02-00"),
             ("00-02-00", "00-02-10"), ("00-05-00", "00-05-10"),
             ("00-08-00", "00-08-10")]
    for a, b in pairs:
        pa, pb = (os.path.join(DONE, f"{n}.png") for n in (a, b))
        if not (os.path.exists(pa) and os.path.exists(pb)):
            print(f"  {a} vs {b}: missing")
            continue
        ga = cv2.cvtColor(cv2.imread(pa), cv2.COLOR_BGR2GRAY).astype(np.int16)
        gb = cv2.cvtColor(cv2.imread(pb), cv2.COLOR_BGR2GRAY).astype(np.int16)
        if ga.shape != gb.shape:
            print(f"  {a} vs {b}: shapes differ")
            continue
        d = np.abs(ga - gb)
        H, W = d.shape
        tiles = []
        for y in range(0, H - 99, 100):
            for x in range(0, W - 99, 100):
                t = d[y:y + 100, x:x + 100]
                tiles.append((int(t.max()), float(t.mean()), y, x))
        mx = sorted(t[0] for t in tiles)
        n = len(mx)
        still = [t for t in tiles if t[0] <= 16]
        print(f"  {a} vs {b}: {n} tiles; per-tile max p10/p50/p90 = "
              f"{mx[n//10]}/{mx[n//2]}/{mx[9*n//10]}; "
              f"{len(still)} tiles fully within the stacked bound (<=16)")
    print("\nfast1 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
