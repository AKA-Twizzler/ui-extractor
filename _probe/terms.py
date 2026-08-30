"""How far off one advance do REAL terminals' rows sit?

Four fresh moments of a video that is nothing but a terminal, measured the
same way as the slides, so the rule that separates them is set from a
population and not from one frame.
"""
import sys, os, glob, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import capture, machine, note_reader, console_reader as cr

VIDEO = "Install Claude Code and-or the AI Memory Vault"
folder = machine.here(f"/mnt/g/Video/{VIDEO}")
mp4 = sorted(glob.glob(os.path.join(folder, "*.mp4")))[0]
out_dir = machine.here(f"/mnt/g/Images/{VIDEO}")

for ts in sys.argv[1:]:
    path, how = capture.capture_moment(mp4, ts, out_dir)
    bgr = cv2.imread(path)
    up = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                    interpolation=cv2.INTER_LANCZOS4)
    big = path.replace(".png", "_3x.png")
    cv2.imwrite(big, up)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    rows = [r for r in note_reader.tess_rows(big, gray) if r["text"].strip()]
    rows.sort(key=lambda r: r["y0"])
    per = []
    for r in rows:
        w = [(x1 - x0) / len(t) for t, x0, x1 in (r.get("words") or [])
             if len(t) >= 3]
        if len(w) >= 2:
            per.append(statistics.median(w))
    got = cr.read_console(path)
    if len(per) < 2:
        print(f"{ts}  too few rows ({len(per)})"); continue
    mid = statistics.median(per)
    worst = max(abs(a - mid) for a in per) / mid
    pooled = cr.advance_of(rows)[1]
    print(f"{ts}  rows {len(per):2d}  pooled {pooled:.3f}  worst row {worst:.3f}"
          f"   read_console={got.get('is_console')}")
    for a in sorted(per, key=lambda v: -abs(v - mid))[:3]:
        print(f"        {a:7.2f}  ({a/mid:5.2f}x)")
