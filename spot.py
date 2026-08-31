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
import machine

import screenness

SAME_SCREEN_DIFF = 4.0   # mean grey change below this and it is the same screen
# ...AND A FIXED LINE IS THE WRONG SHAPE OF ANSWER, which eye tracking learned
# a long time ago. Telling a fixation from a saccade is this same problem in a
# stream of noisy positions, and its oldest method -- I-VT -- is a fixed
# velocity threshold. The reviews are blunt about it: a fixed threshold
# "degrades rapidly under noise", falling under 20% accuracy, while the same
# algorithm with the threshold ADAPTED to the signal's own noise holds above
# 81%. (Review and Evaluation of Eye Movement Event Detection Algorithms,
# PMC9699548; One algorithm to rule them all?, Behavior Research Methods.)
#
# Ours is fixed at 4.0, chosen on a screen recording, and the noise varies by
# twenty times between recordings. Measured on this library's own caches, each
# video's FLOOR -- what it looks like when nothing is happening, the 5th
# percentile of change between consecutive samples:
#
#     a webcam and a chat overlay   7.72     the line is BELOW the floor, so
#                                            every sample is a new screen
#     a live replay                 1.37
#     a screen recording            0.33
#     another screen recording      0.67
#
# The St Jude's replay at its very stillest is already twice the threshold, so
# the test could only ever answer "changed": 1,594 stretches from 1,981
# samples, and one text confirmation per stretch.
#
# So the line is the video's OWN floor times this, and never below the 4.0 that
# already serves a screen recording well. A recording with no camera in it has
# a floor near zero and is pinned at 4.0 whatever this multiplier is, which is
# why it can be raised without touching one. Measured over the four cached
# skims: the webcam stream's stretches fall 1,594 -> 489, and both screen
# recordings keep their exact counts (17 and 17).
#
# WHAT THIS DOES NOT FIX, measured before claiming it did: the MOMENTS barely
# move, 1,594 -> 1,492. Longer stretches just hand the same samples to the
# within-stretch test below, and raising the multiplier further makes it worse
# (x8 gives 1,550). The saving here is in the skim's own reading -- one
# confirmation per stretch, so 489 instead of 1,594 -- not in the read.
FLOOR_TIMES = 2.5
_FLOOR = [None]          # this video's own quiet floor, learned once per scan


def learn_floor(samples):
    """The change this video shows when nothing is happening, from its own
    samples. None where there are too few to tell."""
    if len(samples) < 12:
        _FLOOR[0] = None
        return None
    d = []
    for a, b in zip(samples, samples[1:]):
        ta = np.array(a["thumb"], np.float32)
        tb = np.array(b["thumb"], np.float32)
        d.append(float(np.mean(np.abs(ta - tb))))
    _FLOOR[0] = float(np.percentile(d, 5))
    return _FLOOR[0]


def same_screen_line():
    """The line this video is judged against."""
    f = _FLOOR[0]
    return SAME_SCREEN_DIFF if not f else max(SAME_SCREEN_DIFF, f * FLOOR_TIMES)
UNCERTAIN_BOXES = 20     # OCR boxes needed for an uncertain frame to be a screen

# HOW MUCH INTERFACE MAKES A MOMENT WORTH CAPTURING.
#
# The pixel test cannot tell a dark room from a window. It counts pixels that
# exactly equal their neighbour, on the premise that a camera's noise makes
# ties rare -- and H.264 breaks that premise, painting near-black in flat
# blocks of one value. Measured on 120 frames labelled by eye from six of
# Jared's videos (_probe/screen_truth.json, scored by _probe/scanrule.py): the
# pixel test alone gets 49 of them right and every one of the 20 webcam frames
# wrong, and a spread gate, a step-edge gate and a dilated-ink gate were each
# measured and none of them separates a dark room from a blank window panel.
#
# The reading that follows already settles it -- and the skim then threw the
# evidence away, keeping only WHETHER text was found, not HOW MUCH. Measured
# over the same 120 frames (_probe/boxbar.py), text items per frame:
#
#     a camera        0 (in 30 of 70 frames), then 5 .. 29
#     a screen        14 .. 108
#
# So a webcam with a live chat in the corner reads 5 to 10 items and a screen
# reads dozens. At twelve items no real screen is lost and 109 of the 120 are
# right, against 80 for "any text at all". Twelve is the last value that loses
# nothing: at fifteen, two real screens go.
#
# The bar is on the WHOLE frame's items, not one region's, so a screen made of
# several small windows still clears it -- and a webcam frame with a terminal
# open over it clears it too, which is the point. One did, in the labelled set:
# a Jarvis transcript over the dark room, read at 30 items and kept.
#
# The bar lives HERE rather than in screenness.ui_regions, whose callers
# include the read itself: finding a sparse window is still that function's
# job, and whether the moment is worth capturing is this one's.
WORTH_READING = 12
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
        # THE VERSION IS THE JUDGEMENT'S, not the file format's. A cache
        # written before WORTH_READING carries the old answer to "is this a
        # screen" and would keep it forever, which is how a fix comes to be
        # installed and have no effect. Bump this whenever what the skim
        # DECIDES changes, not only when what it stores does.
        if d.get("every") == every and d.get("video") == video and d.get("v") == 3:
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
            items = sum(r["boxes"] for r in regions)
            confirmed = items >= WORTH_READING
            for s2 in samples:
                if run["start"] <= s2["t"] <= run["end"]:
                    s2["call"] = "screen" if confirmed else "camera"
                    if confirmed:
                        s2["boxes"] = items
                        s2["box"] = regions[0]["box"]
    print(f"  {len(samples)} samples; text read on {checked} of them "
          f"({100*checked/max(1,len(samples)):.0f}%) — one per stretch, "
          f"the rest settled by pixels alone")
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump({"v": 3, "video": video, "every": every, "samples": samples},
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
    return float(np.mean(np.abs(ta - tb))) > same_screen_line()


def stretches(samples):
    learn_floor(samples)
    if os.environ.get("SN_FLOOR") and _FLOOR[0] is not None:
        print("  [this video is still at %.2f grey; a screen changes past %.1f]"
              % (_FLOOR[0], same_screen_line()), file=sys.stderr)
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


# Chronological reading, within a stretch: which samples changed enough to
# read. The whole-thumb mean cannot say -- measured across the library's
# caches, consecutive same-screen samples differ by ~1.0 grey on average,
# because the webcam inset and compression move the frame everywhere -- so
# the thumb is cut into 20x20 cells and each stretch learns its own
# persistently moving cells (the inset), the same shape moving_zones uses on
# full frames. A cell moving in at least half the steps is the stretch's own
# motion; an EVENT is any normally-quiet cell stepping past the bound.
# Measured: quiet cells sit at 0.055 grey median, 0.56 at p90; a typed LINE
# across a cell steps its mean well past 2, a lone short word may not. The
# bound trades compute for completeness and cannot make a wrong claim in
# either direction: every read moment goes through the full pipeline, and an
# extra read is absorbed by the unchanged-pane proof. At 2.0, four in ten
# within-stretch steps read.
CELL = 20
CELL_BOUND = 2.0
CELL_EVERY = 0.5
CELL_BIG = 0.10     # a step that moves a tenth of the thumb is a new moment, moving cells or not


def dense_moments(samples):
    """Per screen stretch: the moments a chronological read should capture --
    the stretch's start, plus every sample where a normally-quiet cell of
    the thumb stepped past the bound."""
    out = []
    for run in stretches(samples):
        if run["call"] != "screen":
            continue
        st = [s for s in samples if run["start"] <= s["t"] <= run["end"]]
        times = [st[0]["t"]]
        if len(st) >= 3:
            thumbs = [np.array(s["thumb"], np.float32) for s in st]
            h, w = thumbs[0].shape
            hc, wc = h // CELL, w // CELL
            steps = np.array([
                np.abs(a - b)[:hc * CELL, :wc * CELL]
                .reshape(hc, CELL, wc, CELL).mean(axis=(1, 3))
                for a, b in zip(thumbs, thumbs[1:])])
            moving = (steps > CELL_BOUND).mean(axis=0) >= CELL_EVERY
            for i, cells in enumerate(steps):
                # A REGION THAT CHANGES OFTEN CAN STILL CHANGE WHOLESALE. The
                # Finder's list at 00:03:00-00:03:50 opened a new folder at
                # every sample, so its cells counted as "moving" and every
                # step inside the stretch was passed over - the Dev folder
                # stood for ten seconds and was never captured. A step that
                # moves a tenth of the thumb is a new screen wherever it
                # falls; the quiet-cell rule still catches the small ones.
                big = (cells > CELL_BOUND).mean() >= CELL_BIG
                if big or (cells[~moving] > CELL_BOUND).any():
                    times.append(st[i + 1]["t"])
        out.append({"start": run["start"], "end": run["end"],
                    "times": sorted(set(times)), "best": run["best"]})
    return out


def hms(s):
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 10
    title = os.path.basename(os.path.dirname(video)) or "capture"
    cache = machine.here(f"/mnt/g/Images/{title}/scan.json")
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
