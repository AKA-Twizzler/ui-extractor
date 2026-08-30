import sys, os, glob
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2
import numpy as np
import screenness, capture, overlay

CASES = [
    ("wallpapered desktop", r"G:\Video\How Claude Code Actually Works", "00:07:29"),
    ("St Jude stream", r"G:\Video\Jarvis Raises Money for St. Judes with Epic Performance - Live Replay July 31, 2026", "03:18:00"),
    ("8-1 stream", r"G:\Video\Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26", "01:15:59"),
]
work = r"G:\Images\_probe_drawn"
os.makedirs(work, exist_ok=True)
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

for name, folder, ts in CASES:
    mp4 = sorted(glob.glob(os.path.join(folder, "*.mp4")))
    if not mp4:
        print("--- %s: no mp4\n" % name); continue
    video = mp4[0]
    path, how = capture.capture_moment(video, ts, work)
    img = cv2.imread(path)
    w0 = screenness.to_working_size(img)
    cells = screenness.cell_scores(w0)
    mask = cells >= screenness.CELL_IS_SCREEN
    print("--- %s  %s   frame %dx%d" % (name, ts, img.shape[1], img.shape[0]))
    print("    the 6x8 grid (# interface, + borderline, . camera):")
    for line in screenness.picture(cells).splitlines():
        print("      " + line)
    regions = screenness.ui_regions(img, eng) or []
    print("    ui_regions kept %d:" % len(regions))
    for r in regions:
        print("      box %s  cells %d  share %.2f  text items %d"
              % (r["box"], r["cells"], r["share"], r.get("boxes", -1)))
    # how many cells does each returned RECTANGLE cover, vs how many are real
    rows, cols = screenness.GRID
    h, w = w0.shape[:2]
    for r in regions:
        x0, y0, x1, y1 = r["box"]
        c0, c1 = x0 * cols // w, max(x0 * cols // w, (x1 - 1) * cols // w)
        r0, r1 = y0 * rows // h, max(y0 * rows // h, (y1 - 1) * rows // h)
        covered = (r1 - r0 + 1) * (c1 - c0 + 1)
        real = int(mask[r0:r1 + 1, c0:c1 + 1].sum())
        print("      rectangle covers %d cells, only %d of them are interface"
              % (covered, real))
    # where does the standing text land
    secs = capture._to_seconds(ts)
    frames = overlay.frames_across(video, secs, workdir=os.path.join(work, "_looks"))
    found = overlay.standing_text(frames, engine=eng)
    back = img.shape[1] / screenness.WORK_WIDTH
    for f in found:
        bx0, by0, bx1, by1 = f["box"]
        cx, cy = (bx0 + bx1) // 2 / back, (by0 + by1) // 2 / back
        cc, rr = int(cx * cols // w), int(cy * rows // h)
        rr = min(rr, rows - 1); cc = min(cc, cols - 1)
        inbox = any(a <= (bx0 + bx1) // 2 < c and b <= (by0 + by1) // 2 < d
                    for a, b, c, d in [tuple(int(v * back) for v in r["box"]) for r in regions])
        print("      %-32s cell(r%d,c%d) score %.2f interface=%s | inside a returned rectangle=%s"
              % (repr(f["text"][:30]), rr, cc, cells[rr, cc], mask[rr, cc], inbox))
    print()
