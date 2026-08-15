#!/usr/bin/env python3
"""Find the moments in a video where a UI is on screen, without watching it all.

Two stages, because grabbing every frame at full quality is enormous waste:

1. SCAN - walk the video at a coarse interval, at reduced size, and score each
   sample for how much readable interface it holds. Cheap enough to run over a
   whole video.
2. CAPTURE - only the moments that scored well are then taken at full quality
   by capture.py, burst-stacked and lossless.

The score is not a guess about content. It counts what an OCR pass actually
finds: how many separate text boxes, how confidently they read, and how many
of them line up in a column, since stacked left-aligned rows are what file
trees, menus and sidebars look like and prose does not.

Run: python3 spot.py <video> [--every 15] [--top 8]
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np


def duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", video],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def sample_frames(video, every, workdir, width=1280):
    """Take one sample every `every` seconds, each seeked to explicitly.

    Each sample is grabbed with its own seek so its timestamp is KNOWN rather
    than inferred from its position in a sequence. Letting ffmpeg thin the
    stream and then counting frames drifts — measured at six seconds on a nine
    minute video — which points the capture at the wrong moment entirely, and
    the frame it returns looks perfectly reasonable while being the wrong shot.
    """
    total = duration(video)
    out = []
    t = 0.0
    while t < total:
        path = os.path.join(workdir, f"s_{int(t):06d}.png")
        r = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
             "-frames:v", "1", "-vf", f"scale={width}:-2", path],
            capture_output=True)
        if r.returncode == 0 and os.path.exists(path):
            out.append((path, int(t)))
        t += every
    return out


def ui_score(engine, path):
    """How much readable, column-aligned interface this frame holds."""
    res, _ = engine(path)
    if not res:
        return 0.0, 0, 0.0
    boxes = [(min(p[0] for p in b), min(p[1] for p in b), t, float(s))
             for b, t, s in res]
    n = len(boxes)
    confs = [s for _, _, _, s in boxes]
    # rows that share a left edge: the signature of a tree, list or menu
    xs = sorted(int(x) for x, _, _, _ in boxes)
    aligned, run = 0, 1
    for a, b in zip(xs, xs[1:]):
        if b - a <= 6:
            run += 1
        else:
            aligned = max(aligned, run)
            run = 1
    aligned = max(aligned, run)
    return n * (aligned / max(1, n)) ** 0.5 * float(np.mean(confs)), n, aligned


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 15
    top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 8
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    total = duration(video)
    print(f"{total/60:.1f} minutes; sampling every {every}s "
          f"(~{int(total/every)} frames instead of {int(total*30)})")
    rows = []
    with tempfile.TemporaryDirectory() as work:
        for path, secs in sample_frames(video, every, work):
            score, n, aligned = ui_score(engine, path)
            rows.append((score, secs, n, aligned))
    rows.sort(reverse=True)
    print(f"\n{'when':>10} {'score':>8} {'text boxes':>11} {'aligned rows':>13}")
    for score, secs, n, aligned in rows[:top]:
        ts = f"{secs//3600:02d}:{secs%3600//60:02d}:{secs%60:02d}"
        print(f"{ts:>10} {score:>8.0f} {n:>11} {aligned:>13}")
    print("\ncapture these with:  python3 capture.py <video> " +
          " ".join(f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d}"
                   for _, s, _, _ in rows[:top]))


if __name__ == "__main__":
    main()
