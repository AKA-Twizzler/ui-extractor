#!/usr/bin/env python3
"""Sweep a library and catalogue the KINDS of interface it contains.

    python3 hunt.py <video-or-folder> [--spots 6]      a few moments each
    python3 hunt.py <video-or-folder> [--every 15]     every distinct screen

Reading one video end to end proves the readers on the screens that video
happens to show. It says nothing about the next one. What decides whether a
library can be read is not how many videos have been walked but how many
DIFFERENT kinds of screen appear in it -- and so far every new kind found has
turned up a fault of its own.

So this does not look for one thing. It samples every video, asks the
instruments what each pane of each frame actually is, and keeps ONE example of
every distinct combination it meets, with the video and the timestamp. What
comes back is a menu of the interfaces the library contains, each with a frame
to calibrate against.

The instruments answer for themselves; nothing here recognises anything:

    tree      the tree reader accepted it
    list      the column reader accepted it
    console   the characters are all ONE width, which is what a terminal is
              and what no proportional interface can be
    document  the note reader got lines out of it
    text      something readable that is none of the above -- an honest
              answer, and the one that marks a kind still to be handled
"""
import os
import subprocess
import sys
import statistics

import cv2
import numpy as np

import columns
import machine
import note_reader
import panes
import screenness
import spot
import tree_reader

VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".m4v")
HUNT_WIDTH = 1920      # deciding WHAT a frame holds needs far less than 4K
MONO_SPREAD = 0.04     # below this every character is one width

# The number is measured. On the frames to hand a terminal scores 0.015, an
# Obsidian note 0.094, a Finder list 0.166 and a sidebar tree 0.078: monospace
# sits an order of magnitude below anything proportional.


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


def frame_at(path, secs, out_png):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                    "-ss", f"{secs:.2f}", "-i", path, "-frames:v", "1",
                    out_png], check=False)
    return out_png if os.path.exists(out_png) else None


def hms(secs):
    s = int(secs)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def theme_of(bgr, regions):
    """Light or dark, from the interface's own pixels rather than the frame's.

    A dark video with a light window in it is a light interface, and asking
    the whole frame would answer the opposite.
    """
    if not regions:
        return None
    work = screenness.to_working_size(bgr)
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    vals = []
    for r in regions:
        x0, y0, x1, y1 = r["box"]
        crop = g[y0:y1, x0:x1]
        if crop.size:
            vals.append(float(np.median(crop)))
    if not vals:
        return None
    return "light" if float(np.median(vals)) >= 128 else "dark"


def char_spread(big_path, gray):
    """How much the width of a character varies across this pane.

    A terminal sets every character on the same advance, so the spread is
    almost nothing. No proportional interface can do that. This is the one
    test that separates a console from a document, and it is a measurement
    rather than a look-up of fonts.
    """
    widths = []
    for r in note_reader.tess_rows(big_path, gray):
        for text, x0, x1 in (r.get("words") or []):
            if len(text) >= 3:
                widths.append((x1 - x0) / len(text))
    if len(widths) < 20:
        return None
    mid = statistics.median(widths)
    if mid <= 0:
        return None
    return statistics.median([abs(w - mid) for w in widths]) / mid


def classify(pane_path):
    """What this pane is, in the instruments' own words."""
    try:
        tree = tree_reader.read_tree(pane_path)
        if tree.get("is_tree") and len(tree["rows"]) >= 5:
            return "tree"
    except Exception:
        pass
    try:
        lst = columns.read_list(pane_path)
        if lst.get("is_list"):
            return "list"
    except Exception:
        pass
    try:
        bgr = cv2.imread(pane_path)
        if bgr is None:
            return None
        big = pane_path.replace(".png", "_3x.png")
        if not os.path.exists(big):
            up = machine.enlarge(bgr, 3)
            cv2.imwrite(big, up)
        gray = cv2.cvtColor(cv2.imread(big), cv2.COLOR_BGR2GRAY)
        spread = char_spread(big, gray)
        if spread is None:
            return None
        if spread < MONO_SPREAD:
            return "console"
        note = note_reader.read_note(pane_path)
        if note["markdown"].strip().count("\n") >= 3:
            return "document"
        return "text"
    except Exception:
        return None


def look(png, engine):
    """The kinds of pane this frame holds, and whether it is light or dark."""
    img = cv2.imread(png)
    if img is None:
        return None
    if img.shape[1] > HUNT_WIDTH:
        h = int(img.shape[0] * HUNT_WIDTH / img.shape[1])
        img = cv2.resize(img, (HUNT_WIDTH, h), interpolation=cv2.INTER_AREA)
        cv2.imwrite(png, img)
    regions = screenness.ui_regions(img, engine)
    if not regions:
        return {"ui": False}
    kinds = []
    for pi, (px0, px1) in enumerate(panes.pane_columns(img, engine=engine)):
        pane_path = png.replace(".png", f"_c{pi}.png")
        # Enlarged as the readers expect. Writing panes at native size was
        # tried, to keep a narrow pane from being blown up sevenfold and then
        # threefold again for measurement -- and it silently broke the whole
        # census: at native size the text is too small to read, so every pane
        # came back as nothing and nine videos in a row reported no interface
        # at all. Cheap and blind is worse than slow and right.
        if panes.write_pane(img, px0, px1, pane_path) is None:
            continue
        kind = classify(pane_path)
        if kind:
            kinds.append(kind)
        for junk in (pane_path, pane_path.replace(".png", "_3x.png")):
            if os.path.exists(junk):
                os.remove(junk)
    return {"ui": True, "theme": theme_of(img, regions), "kinds": kinds}


def keep_frame(video, secs, png):
    """Save the example beside its video's other frames, named by its moment."""
    title = os.path.basename(os.path.dirname(video))
    out_dir = os.path.join(machine.here("/mnt/g/Images"), title)
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, hms(secs).replace(":", "-") + ".png")
    if not os.path.exists(dest):
        img = cv2.imread(png)
        if img is not None:
            cv2.imwrite(dest, img)
    return dest


def spot_check(video, count, work, engine, seen):
    """Look at a handful of moments spread through a video, and no more.

    Mapping a video to every screen it shows is the right thing when that
    video is being READ. It is the wrong thing when the question is only
    "what kinds of interface does this library contain" -- the map costs
    minutes a video and forty-three of them is an afternoon, to answer a
    question a few moments from each would have answered.

    So this takes `count` moments spread evenly through each video, skipping
    the first and last tenth where titles and end cards live, and keeps only
    the kinds it has not seen before.
    """
    total = duration(video)
    if total <= 0:
        return
    title = os.path.basename(os.path.dirname(video)) or os.path.basename(video)
    print(f"# {title}", flush=True)
    for k in range(count):
        secs = total * (0.1 + 0.8 * (k + 0.5) / count)
        png = frame_at(video, secs, os.path.join(work, "spot.png"))
        if not png:
            continue
        got = look(png, engine)
        if not (got and got.get("ui") and got["kinds"]):
            continue
        sig = (got["theme"], tuple(sorted(set(got["kinds"]))))
        if sig in seen:
            continue
        seen[sig] = (title, hms(secs))
        keep_frame(video, secs, png)
        print(f"NEW  {title}  {hms(secs)}  {got['theme']}  "
              + " + ".join(sorted(set(got['kinds']))), flush=True)


def sweep(video, every, work, engine, seen):
    """Classify one frame per DISTINCT screen, not one per sample.

    Sampling on a fixed clock and reading every sample is waste: a video sits
    on the same screen for minutes at a time, and reading it again tells us
    nothing we did not have. The video map already answers where the screen
    CHANGES, cheaply, so only those moments are read -- which is the same
    method the capture step uses, on the same cache.
    """
    title = os.path.basename(os.path.dirname(video)) or os.path.basename(video)
    out_dir = os.path.join(machine.here("/mnt/g/Images"), title)
    os.makedirs(out_dir, exist_ok=True)
    try:
        samples = spot.scan(video, every, os.path.join(out_dir, "scan.json"))
    except Exception as exc:
        print(f"  (could not map {title}: {str(exc)[:60]})", flush=True)
        return
    runs = [r for r in spot.stretches(samples) if r["call"] == "screen"]
    print(f"# {title} -- {len(runs)} distinct screens", flush=True)
    for r in runs:
        secs = r["best"]["t"]
        png = frame_at(video, secs, os.path.join(work, "census.png"))
        if not png:
            continue
        got = look(png, engine)
        if not (got and got.get("ui") and got["kinds"]):
            continue
        sig = (got["theme"], tuple(sorted(set(got["kinds"]))))
        if sig in seen:
            continue
        seen[sig] = (title, hms(secs))
        keep_frame(video, secs, png)
        print(f"NEW  {title}  {hms(secs)}  {got['theme']}  "
              + " + ".join(sorted(set(got['kinds']))), flush=True)


def main():
    target = sys.argv[1]
    every = float(sys.argv[sys.argv.index("--every") + 1]) \
        if "--every" in sys.argv else 15.0
    work = os.environ.get("HUNT_WORK", "/tmp")
    videos = []
    if os.path.isdir(target):
        for root, _, files in os.walk(target):
            for f in sorted(files):
                if f.lower().endswith(VIDEO_EXT):
                    videos.append(os.path.join(root, f))
    else:
        videos = [target]
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    seen = {}
    spots = int(sys.argv[sys.argv.index("--spots") + 1]) \
        if "--spots" in sys.argv else 0
    for v in videos:
        if spots:
            spot_check(v, spots, work, engine, seen)
        else:
            sweep(v, every, work, engine, seen)
    print("\n=== the kinds of screen in this library ===", flush=True)
    for (theme, kinds), (title, ts) in sorted(seen.items(), key=lambda kv: str(kv[0])):
        print(f"  {theme:5s}  {' + '.join(kinds):28s}  {title}  {ts}", flush=True)


if __name__ == "__main__":
    main()
