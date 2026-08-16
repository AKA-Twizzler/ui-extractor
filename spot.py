#!/usr/bin/env python3
"""Map a video: where there is an interface, where it changes, what to capture.

The aim is to not waste effort. Ten minutes is eighteen thousand frames, most
of them either somebody talking or the same screen sitting still. What is worth
capturing is one frame per DISTINCT screen and nothing else.

How it decides, cheapest test first:

  1. Where could interface be?  A camera sensor puts noise on every pixel, so
     neighbouring pixels are almost never exactly equal; anything rendered
     paints flat areas with one exact value. Counting exact ties costs almost
     nothing and proposes regions, per part of the frame — so a caption bar or
     a file window filling a corner of a camera shot is still found.
  2. Is that region really interface?  Only the proposed regions are read, and
     only they. A blank wall is flat too; what makes a region interface is
     that it CARRIES TEXT. Frames with no candidate region are never read at
     all, which is most of the talking ones.
  3. Has the screen changed?  Consecutive samples are compared as pictures.
     No reading is needed to know one screen became a different screen.

Only the moments that survive all that are captured at full quality.

Run: python3 spot.py <video> [--every 10] [--map] [--rescan]
"""
import json
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

import screenness

SAME_SCREEN_DIFF = 4.0   # mean grey change below this and it is the same screen
UNCERTAIN_BOXES = 20     # OCR boxes needed for an uncertain frame to be a screen
THUMB = (320, 180)
# The comparison picture has to be big enough to SEE a change. At 80x45 a
# different note open in the same window is pixel-identical, so a ten minute
# Obsidian session came back as two screens: consecutive change measured 0.31
# on average while the layout never moved.


def duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", video],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def sample_frames(video, every, workdir):
    """One sample every `every` seconds, each seeked to explicitly.

    Each sample is seeked to so its timestamp is KNOWN rather than inferred
    from a position in a sequence. Letting ffmpeg thin the stream and counting
    frames drifted six seconds over nine minutes when measured, which points
    the capture at the wrong scene while looking perfectly reasonable.
    """
    total = duration(video)
    t = 0.0
    while t < total:
        path = os.path.join(workdir, f"s_{int(t):06d}.png")
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
             "-frames:v", "1", "-vf", f"scale={screenness.WORK_WIDTH}:-2", path],
            capture_output=True)
        if r.returncode == 0 and os.path.exists(path):
            yield path, int(t)
        t += every


def scan(video, every, cache_path=None, rescan=False):
    if cache_path and os.path.exists(cache_path) and not rescan:
        d = json.load(open(cache_path))
        if d.get("every") == every and d.get("video") == video and d.get("v") == 2:
            return d["samples"]

    samples = []
    keep = {}
    with tempfile.TemporaryDirectory() as work:
        for path, secs in sample_frames(video, every, work):
            bgr = cv2.imread(path)
            if bgr is None:
                continue
            cands = screenness.candidate_regions(bgr)
            share = sum(c["share"] for c in cands)
            thumb = cv2.resize(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), THUMB,
                               interpolation=cv2.INTER_AREA)
            samples.append({"t": secs, "call": "screen" if cands else "camera",
                            "frac": share, "regions": len(cands),
                            "box": cands[0]["box"] if cands else None,
                            "boxes": 0, "thumb": thumb.tolist()})
            if cands:
                keep[secs] = path
        # confirm by reading, but ONCE PER STRETCH rather than once per sample.
        # Inside a run of one screen every extra read says what the first said.
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        by_t = {s["t"]: s for s in samples}
        checked = 0
        for run in stretches(samples):
            if run["call"] != "screen":
                continue
            best = run["best"]
            path = keep.get(best["t"])
            if path is None:
                continue
            regions = screenness.ui_regions(cv2.imread(path), engine)
            checked += 1
            confirmed = bool(regions)
            for s2 in samples:
                if run["start"] <= s2["t"] <= run["end"]:
                    s2["call"] = "screen" if confirmed else "camera"
                    if confirmed:
                        s2["boxes"] = regions[0]["boxes"]
                        s2["box"] = regions[0]["box"]
    print(f"  {len(samples)} samples; text read on {checked} of them "
          f"({100*checked/max(1,len(samples)):.0f}%) — one per stretch, "
          f"the rest settled by pixels alone")
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump({"v": 2, "video": video, "every": every, "samples": samples},
                  open(cache_path, "w"))
    return samples


def changed(a, b):
    """Is this a different screen from the one the stretch started on.

    Compared against the stretch's OWN first sample, never against the sample
    immediately before. Screens drift: a note scrolls a line, a folder opens,
    a pane resizes. Judged step by step every change looks small and a whole
    video collapses into one stretch — measured, a ten minute recording came
    back as two screens. Judged against where the stretch began, drift adds up
    and the split lands where the screen genuinely became another one.
    """
    ta = np.array(a["thumb"], np.float32)
    tb = np.array(b["thumb"], np.float32)
    return float(np.mean(np.abs(ta - tb))) > SAME_SCREEN_DIFF


def stretches(samples):
    runs = []
    for s in samples:
        new = (not runs
               or runs[-1]["call"] != s["call"]
               or (s["call"] == "screen" and changed(runs[-1]["anchor"], s)))
        if new:
            runs.append({"call": s["call"], "start": s["t"], "end": s["t"],
                         "anchor": s, "last": s, "best": s})
        else:
            runs[-1]["end"] = s["t"]
            runs[-1]["last"] = s
            if s["frac"] > runs[-1]["best"]["frac"]:
                runs[-1]["best"] = s
    return runs


def hms(s):
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 10
    title = os.path.basename(os.path.dirname(video)) or "capture"
    cache = f"/mnt/g/Images/{title}/scan.json"
    total = duration(video)
    print(f"{total/60:.1f} minutes; {int(total/every)} samples instead of "
          f"{int(total*30)} frames")
    samples = scan(video, every, cache, rescan="--rescan" in sys.argv)

    runs = stretches(samples)
    ui = [r for r in runs if r["call"] == "screen"]
    none = [r for r in runs if r["call"] == "camera"]
    ui_time = sum(r["end"] + every - r["start"] for r in ui)
    print(f"\n{'from':>9}  {'to':>9}   ")
    for r in runs:
        mins = (r["end"] + every - r["start"]) / 60
        if r["call"] == "screen":
            share = r["best"]["frac"] * 100
            how = "full screen" if share > 60 else f"part of frame ({share:.0f}%)"
            label = f"UI - {how}"
        else:
            label = "no UI (real-life camera only)"
        print(f"{hms(r['start']):>9}  {hms(r['end']+every):>9}   {label:<30} "
              f"({mins:.1f} min)")
    print(f"\n{ui_time/60:.1f} of {total/60:.1f} minutes hold interface; "
          f"{len(ui)} distinct screens to capture, {len(none)} stretches with none")
    if ui:
        print("\none capture per distinct screen:")
        for r in ui:
            b = r["best"]
            box = b.get("box")
            where = (f"x{box[0]}-{box[2]} y{box[1]}-{box[3]}" if box else "")
            print(f"   {hms(b['t'])}   {b['frac']*100:3.0f}% of frame   "
                  f"{b['boxes']:>3} text items   {where}")
        print("\n  python3 capture.py <video> " +
              " ".join(hms(r["best"]["t"]) for r in ui))


if __name__ == "__main__":
    main()
