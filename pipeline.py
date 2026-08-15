#!/usr/bin/env python3
"""Point this at a video and get back what its interfaces show.

    python3 pipeline.py <video> [--every 10] [--limit 12]

It maps the video, captures one frame per distinct screen, and reads whatever
it can from each: the file tree where there is one, the text where there is
not. Everything it cannot settle is reported as unsettled rather than guessed.
"""
import os
import sys

import cv2
import numpy as np

import capture
import screenness
import spot
import tree_reader
import verify_names


def pane_columns(img, min_width=90):
    """Split a window into its panes at the vertical borders it draws.

    A pane border runs the full height of the window, which no text or icon
    ever does. Splitting there matters: handed a whole Obsidian window, the
    tree reader correctly refuses, because a note's prose lines do not sit on
    the sidebar's row pitch. Each pane has to be read as itself.
    """
    work = screenness.to_working_size(img)
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    k = np.ones((1, 41), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    cov = (cv2.max(lighter, darker) > 4).mean(axis=0)
    edges = [x for x, v in enumerate(cov) if v >= 0.75]
    cuts, w = [0], work.shape[1]
    for x in edges:
        if x - cuts[-1] >= min_width:
            cuts.append(x)
    cuts.append(w)
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a >= min_width]


def write_pane(img, x0, x1, path, target=1400):
    """Cut the pane out of the ORIGINAL frame, not the shrunken working copy.

    The pane boundaries are found on a small copy because that is cheap, but
    the pixels must come from the full-size frame. Cropping the small copy and
    enlarging it again destroys exactly the fine text this is here to read —
    measured, it turned clean names into "Beyond the Baoics" and "Emall Gueue".
    """
    scale_back = img.shape[1] / screenness.WORK_WIDTH
    nx0, nx1 = int(x0 * scale_back), int(x1 * scale_back)
    pane = img[:, max(0, nx0):min(img.shape[1], nx1)]
    if pane.size == 0 or pane.shape[1] < 40:
        return False
    scale = max(1, int(target / pane.shape[1]))
    if scale > 1:
        pane = cv2.resize(pane, (pane.shape[1] * scale, pane.shape[0] * scale),
                          interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(path, pane)
    return True


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 10
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 12
    title = os.path.basename(os.path.dirname(video)) or "capture"
    out_dir = f"/mnt/g/Images/{title}"
    cache = f"{out_dir}/scan.json"

    print(f"=== {title} ===")
    samples = spot.scan(video, every, cache, rescan="--rescan" in sys.argv)
    runs = [r for r in spot.stretches(samples) if r["call"] == "screen"]
    print(f"{len(runs)} distinct screens found; capturing "
          f"{min(limit, len(runs))}\n")

    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()

    for r in runs[:limit]:
        secs = r["best"]["t"]
        ts = spot.hms(secs)
        path, how = capture.capture_moment(video, ts, out_dir)
        img = cv2.imread(path)
        regions = screenness.ui_regions(img, engine)
        share = sum(x["share"] for x in regions) * 100
        print(f"--- {ts}  ({how}; interface on {share:.0f}% of the frame) ---")
        if not regions:
            print("    no readable interface at full size\n")
            continue

        for pi, (px0, px1) in enumerate(pane_columns(img)):
            pane_path = f"{out_dir}/{ts.replace(':','-')}_pane{pi}.png"
            if not write_pane(img, px0, px1, pane_path):
                continue
            tree = tree_reader.read_tree(pane_path)
            if tree.get("is_tree") and len(tree["rows"]) >= 5:
                tree = verify_names.verify(pane_path, tree)
                print(f"  [pane {pi}: a file tree]")
                print(tree_reader.render(tree))
                flagged = [x for x in tree["rows"]
                           if x["name_status"] not in ("confident", "reconciled")]
                if flagged:
                    print("    unsettled: " + "; ".join(
                        f"{x['name_primary']!r}/{x['name_second']!r}"
                        for x in flagged))
            else:
                res, _ = engine(pane_path)
                texts = [t for _, t, _ in (res or [])]
                if len(texts) < 4:
                    continue
                print(f"  [pane {pi}: text, not a tree]")
                print("    " + " | ".join(texts[:16]))
        print()


if __name__ == "__main__":
    main()
