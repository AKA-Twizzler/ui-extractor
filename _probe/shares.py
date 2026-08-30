import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, checks, screenness, overlay
eng = checks.engine()
CASES = [("stjude","02:12:59","donation card, must keep"),
         ("aug03","00:09:00","livestream-ended cards, must keep"),
         ("july6","00:55:00","chat popups on a live"),
         ("works","00:01:52","desktop + Finder"),
         ("jarvis","00:02:00","desktop")]
for key, stamp, what in CASES:
    p = checks.frame(key, stamp)
    img = cv2.imread(p)
    regs = screenness.ui_regions(img, eng)
    share = sum(r["share"] for r in regs) * 100
    pans = overlay.read_overlays(p, eng)["panels"]
    print(f"{what[:34]:36} share={share:5.1f}%  panels={len(pans)}")
