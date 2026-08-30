"""Do the wrongly-claimed standing strings sit inside drawn windows?

Fault 3: on the works desktop, "Size", "Locations", "Har" and a date are
reported as text drawn on the camera. The candidate gate: text whose box sits
inside a window found by its four drawn sides is the window's own chrome.
Verify the geometry on the real frames before building it:
  - the three strings' OCR boxes fall inside overlay.windows() boxes on the
    first LOOK frame (standing_text measures on shots[0], not the capture)
  - the jaredrhod.com banner falls inside NO window on the stream's look
"""
import glob
import sys
import cv2

sys.path.insert(0, ".")
import overlay

WORKS = "G:/Images/How Claude Code Actually Works"
STJUDE = ("G:/Images/Jarvis and Jaredrhod Raise Money for St. Jude's "
          "Children's Hospital - Live Replay 8-1-26")


def show(tag, path, needles):
    bgr = cv2.imread(path)
    if bgr is None:
        print(f"{tag}: MISSING {path}")
        return
    wins = overlay.windows(bgr)
    print(f"{tag}: {path.split('/')[-1]}  {bgr.shape[1]}x{bgr.shape[0]}")
    for w in wins:
        print(f"   window {w}")
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    res, _ = eng(path)
    for box, text, _ in (res or []):
        low = text.strip().lower()
        if not any(n in low for n in needles):
            continue
        x0 = int(min(p[0] for p in box)); x1 = int(max(p[0] for p in box))
        y0 = int(min(p[1] for p in box)); y1 = int(max(p[1] for p in box))
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        inside = any(a <= cx < c and b <= cy < d for a, b, c, d in wins)
        print(f"   {text.strip()[:40]!r:44} at {x0},{y0}-{x1},{y1}  "
              f"{'INSIDE a window' if inside else 'in no window'}")


looks = sorted(glob.glob(WORKS + "/_looks/look_*.png"))
print(f"works _looks: {len(looks)} frames")
for p in looks:
    show("works look", p, ("size", "locations", "har", "jaredrhod"))
print()
looks = sorted(glob.glob(STJUDE + "/_looks/look_*.png"))
print(f"stjude _looks: {len(looks)} frames")
if looks:
    show("stjude look", looks[0], ("jaredrhod",))
