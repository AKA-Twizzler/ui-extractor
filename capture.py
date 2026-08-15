#!/usr/bin/env python3
"""Take frames out of a video at named moments, as cleanly as the source allows.

Two things matter here and neither is obvious:

1. Frames are written as PNG, never JPEG. The source is already a compressed
   video; saving the grab as JPEG compresses it a second time, and the detail
   lost is exactly the fine text this job exists to read.

2. A moment is captured as a short BURST and the frames are median-stacked,
   not grabbed as a single frame. On a still screen every frame shows the same
   picture with different compression noise, so the median of the burst keeps
   what is really there and drops what the encoder invented. If the screen is
   moving, the burst is detected as moving and the single sharpest frame is
   used instead, because stacking motion would smear it.

3. A burst never crosses a cut. Video cuts between shots, and a burst centred
   on a moment can straddle one, so half its frames show a different scene
   entirely. The burst is split at any jump too large to be content changing,
   and only the shot containing the requested moment is kept. Without this the
   sharpest-frame rule can hand back a frame from the wrong shot, which is a
   silent and very convincing kind of wrong.

Run: python3 capture.py <video> <HH:MM:SS> [more timestamps...] --out DIR
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

BURST_SECONDS = 1.5
STILL_THRESHOLD = 1.5     # mean grey levels of frame-to-frame change
CUT_THRESHOLD = 12.0      # above this, the picture changed shot, not content


def _ffmpeg_burst(video, timestamp, seconds, workdir):
    start = max(0.0, _to_seconds(timestamp) - seconds / 2)
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", video,
           "-t", f"{seconds:.3f}", "-vsync", "0",
           os.path.join(workdir, "f_%04d.png")]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(os.path.join(workdir, f) for f in os.listdir(workdir)
                  if f.startswith("f_"))


def _to_seconds(ts):
    parts = [float(p) for p in str(ts).split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def _slug(ts):
    s = _to_seconds(ts)
    return f"{int(s // 3600):02d}-{int(s % 3600 // 60):02d}-{int(s % 60):02d}"


def capture_moment(video, timestamp, out_dir, seconds=BURST_SECONDS):
    """Return (path, how) for one moment: how is 'stacked' or 'sharpest'."""
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        files = _ffmpeg_burst(video, timestamp, seconds, work)
        if not files:
            raise RuntimeError(f"no frames at {timestamp}")
        frames = [cv2.imread(f, cv2.IMREAD_COLOR) for f in files]
        frames = [f for f in frames if f is not None]
        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        moves = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))
                 for a, b in zip(grays, grays[1:])]

        # keep only the shot the requested moment belongs to
        target = len(frames) // 2
        lo, hi = 0, len(frames)
        for i, m in enumerate(moves):
            if m >= CUT_THRESHOLD:
                if i + 1 <= target:
                    lo = i + 1
                else:
                    hi = i + 1
                    break
        cuts = sum(1 for m in moves if m >= CUT_THRESHOLD)
        frames, grays = frames[lo:hi], grays[lo:hi]
        moves = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))
                 for a, b in zip(grays, grays[1:])]
        still = (max(moves) < STILL_THRESHOLD) if moves else True
        if still and len(frames) >= 3:
            out = np.median(np.stack(frames).astype(np.float32), axis=0).astype(np.uint8)
            how = f"stacked {len(frames)} still frames"
        else:
            sharp = [cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]
            out = frames[int(np.argmax(sharp))]
            how = f"sharpest of {len(frames)} moving frames"
        if cuts:
            how += f"; burst crossed {cuts} cut(s), kept the moment's own shot"
        path = os.path.join(out_dir, f"{_slug(timestamp)}.png")
        cv2.imwrite(path, out, [cv2.IMWRITE_PNG_COMPRESSION, 3])
        return path, how


def panes(png_path, min_height=0.75):
    """The vertical dividers the window draws, as x positions.

    A pane border is a column lit down almost the whole window, which is the
    one thing no text or icon ever is. The sidebar is the band between the
    first two.
    """
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    bg = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((1, 41), np.uint8))
    diff = cv2.subtract(img, bg)
    cov = (diff > 4).mean(axis=0)
    return [x for x, v in enumerate(cov) if v >= min_height]


def main():
    args = [a for a in sys.argv[1:] if a != "--out"]
    out_dir = None
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]
        args = [a for a in args if a != out_dir]
    video, stamps = args[0], args[1:]
    if out_dir is None:
        title = os.path.basename(os.path.dirname(video)) or "capture"
        out_dir = f"/mnt/g/Images/{title}"
    for ts in stamps:
        path, how = capture_moment(video, ts, out_dir)
        print(f"{ts} -> {path}  ({how})")


if __name__ == "__main__":
    main()
