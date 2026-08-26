"""How completely do the words either side of a gap answer each other?"""
import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, panes, screenness

eng = checks.engine()
for key, stamp, box in (("jarvis", "00:02:00", (1, 44, 1940, 2157)),
                        ("jarvis", "00:02:00", (1931, 44, 3826, 2157)),
                        ("memfiles", "00:00:00", (1811, 494, 3192, 1148)),
                        ("memfiles", "00:00:00", (184, 472, 1760, 1140))):
    img = cv2.imread(checks.frame(key, stamp))
    crop = img[box[1]:box[3], box[0]:box[2]]
    work = screenness.to_working_size(crop)
    gaps, _spans, words = panes.text_gaps(work, eng, boxes=True)
    print("=== %s %s %s  gaps at %s" % (key, stamp, box, gaps))
    for x in gaps:
        left = [b for b in words if b[2] <= x]
        right = [b for b in words if b[0] >= x]
        def bands(bs):
            out = []
            for b in sorted(bs, key=lambda b: b[1] + b[3]):
                mid, high = (b[1] + b[3]) / 2.0, max(1.0, float(b[3] - b[1]))
                if out and mid - out[-1][0] <= 0.6 * high:
                    continue
                out.append((mid, high))
            return out
        here, there = bands(left), bands(right)
        if not here or not there:
            print("    x=%4d  one side empty (%d/%d words)" % (x, len(left), len(right)))
            continue
        highs = sorted(h for _m, h in here + there)
        row = highs[len(highs) // 2]
        hit = sum(1 for m, _h in here
                  if any(abs(m - n) <= 0.5 * row for n, _h2 in there))
        print("    x=%4d  rows %3d | %3d   matched %3d  = %.2f of the smaller"
              % (x, len(here), len(there), hit, hit / max(1, min(len(here), len(there)))))
