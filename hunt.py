#!/usr/bin/env python3
"""Find the frames worth calibrating against, across a whole library.

    python3 hunt.py <video-or-folder> [--every 20] [--what list|light|tree]

Some things cannot be proven without an example: a Finder-style window with
Name, Date Modified, Size and Kind, or a file tree drawn in a light theme.
Hunting for them by watching hours of video is not the job. The instruments
already know what they are looking at, so they do the hunting: each sampled
frame is asked whether it holds an interface, whether that interface is light
or dark, and whether any of its panes reads as a tree or as a table.

Only the answers are printed -- video, timestamp, and what was found -- so a
library can be swept once and the interesting moments picked out by eye.
"""
import os
import subprocess
import sys

import cv2
import numpy as np

import columns
import note_reader
import screenness
import tree_reader

VIDEO_EXT = (".mp4", ".mkv", ".mov", ".webm", ".m4v")


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


def theme_of(img, regions):
    """Light or dark, from the interface's own pixels rather than the frame's.

    A dark video with a light window in it is a light interface, and asking
    the whole frame would answer the opposite.
    """
    # the region boxes are in the WORKING copy's coordinates, so the theme
    # must be read there too, or the crop lands somewhere else entirely
    work = screenness.to_working_size(img)
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    if not regions:
        return None
    vals = []
    for r in regions:
        x0, y0, x1, y1 = r["box"]
        vals.append(float(np.median(g[y0:y1, x0:x1])))
    return "light" if float(np.median(vals)) >= 128 else "dark"


def look(png, engine):
    """What this frame holds: nothing, a tree, a table, or plain interface."""
    img = cv2.imread(png)
    if img is None:
        return None
    regions = screenness.ui_regions(img, engine)
    if not regions:
        return {"ui": False}
    found = {"ui": True, "theme": theme_of(img, regions), "panes": []}
    from panes import pane_columns, write_pane
    for pi, (px0, px1) in enumerate(pane_columns(img, engine=engine)):
        pane_path = png.replace(".png", f"_h{pi}.png")
        if write_pane(img, px0, px1, pane_path) is None:
            continue
        try:
            tree = tree_reader.read_tree(pane_path)
            if tree.get("is_tree") and len(tree["rows"]) >= 5:
                found["panes"].append(("tree", len(tree["rows"])))
                continue
            lst = columns.read_list(pane_path)
            if lst.get("is_list"):
                found["panes"].append(("list", lst["columns"]))
                continue
        except Exception as exc:
            found["panes"].append(("error", str(exc)[:40]))
        finally:
            for junk in (pane_path, pane_path.replace(".png", "_3x.png")):
                if os.path.exists(junk):
                    os.remove(junk)
    return found


def sweep(video, every, work, engine):
    total = duration(video)
    name = os.path.basename(os.path.dirname(video)) or os.path.basename(video)
    secs = 0.0
    while secs < total:
        png = frame_at(video, secs, os.path.join(work, "hunt.png"))
        if png:
            got = look(png, engine)
            if got and got.get("ui"):
                kinds = got["panes"]
                lists = [n for k, n in kinds if k == "list"]
                trees = [n for k, n in kinds if k == "tree"]
                if lists or (trees and got["theme"] == "light"):
                    bits = []
                    if lists:
                        bits.append(f"list with {max(lists)} columns")
                    if trees:
                        bits.append(f"{got['theme']} tree, {max(trees)} rows")
                    print(f"{name}  {hms(secs)}  " + "; ".join(bits), flush=True)
        secs += every


def main():
    target = sys.argv[1]
    every = float(sys.argv[sys.argv.index("--every") + 1]) \
        if "--every" in sys.argv else 20.0
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
    for v in videos:
        sweep(v, every, work, engine)


if __name__ == "__main__":
    main()
