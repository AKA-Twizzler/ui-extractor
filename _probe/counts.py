"""How many rectangles each finder closes on every fixture frame."""
import re, sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, overlay, shapes

src = open(r"/home/trism/.claude/jobs/014c964f/tmp/replay\checks.py", encoding="utf-8").read()
pairs = sorted(set(re.findall(r'(?:regions|frame)\(\s*"([a-z0-9]+)"\s*,\s*"([0-9:]+)"', src)))
print("%-10s %-9s %5s %5s   %s" % ("video", "at", "over", "shape", "shapes boxes (% of screen)"))
for key, stamp in pairs:
    try:
        p = checks.frame(key, stamp)
        img = cv2.imread(p)
        if img is None:
            print("%-10s %-9s  no frame" % (key, stamp)); continue
        h, w = img.shape[:2]
        o = [tuple(int(v) for v in r[:4]) for r in overlay.windows(img)]
        s = [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
        share = ["%.0f%%" % (100.0 * (b[2]-b[0]) * (b[3]-b[1]) / (w*h)) for b in s]
        print("%-10s %-9s %5d %5d   %s" % (key, stamp, len(o), len(s), " ".join(share)))
    except Exception as e:
        print("%-10s %-9s  ERROR %s" % (key, stamp, e))
