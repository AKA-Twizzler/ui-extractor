"""Two ways at once: every window the screen drew must be in the picture,
and every box the picture draws must be a window the screen drew.

against.py answers "is this box on SOME rectangle". This answers the two
questions that matter: what did the picture MISS, and what did it INVENT.
"""
import json, os, re, sys
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay")
import selfcheck as SC
import windows_of

NOTE = sys.argv[1]
FRAMES = sys.argv[2]
RECS = sys.argv[3] if len(sys.argv) > 3 else None


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / max(1e-6, ua)


def pct(r, W, H):
    return [100.0*r[0]/W, 100.0*r[1]/H, 100.0*r[2]/W, 100.0*r[3]/H]


lines = open(NOTE, encoding="utf-8").read().split("\n")
tot_miss = tot_extra = tot_ok = 0
for k, ln in enumerate(lines, 1):
    st = re.search(r'class="sn-stamp">([\d:]+)(?: to ([\d:]+))?', ln)
    if not st or "sn-stage" not in ln:
        continue
    lo, hi = st.group(1), st.group(2) or st.group(1)
    frame = os.path.join(FRAMES, lo.replace(":", "-") + ".png")
    if not os.path.exists(frame):
        continue
    real = windows_of.windows(frame)
    W, H = 3840.0, 2160.0
    drawn = []
    for cls, kind in (("sn-slot", "filled"), ("sn-ghost", "outline")):
        for (p, _) in SC._boxes(ln, cls):
            drawn.append(([p[0], p[1], p[0]+p[2], p[1]+p[3]], kind))
    said = [pct(r, W, H) for r in real]
    used = set()
    print("=== %s  (line %d)  %d windows on the frame, %d boxes drawn"
          % (lo, k, len(said), len(drawn)))
    for i, r in enumerate(said):
        best, bi = 0.0, None
        for j, (b, kind) in enumerate(drawn):
            v = iou(r, b)
            if v > best:
                best, bi = v, j
        if best > 0.7:
            used.add(bi)
            tot_ok += 1
            print("   ok      window l %5.1f t %5.1f r %5.1f b %5.1f  drawn %s %.2f"
                  % (r[0], r[1], r[2], r[3], drawn[bi][1], best))
        else:
            tot_miss += 1
            print("   MISSED  window l %5.1f t %5.1f r %5.1f b %5.1f  best %.2f"
                  % (r[0], r[1], r[2], r[3], best))
    for j, (b, kind) in enumerate(drawn):
        if j in used:
            continue
        # a box covering the whole screen is a window filling the screen,
        # which draws no border for the frame to measure
        if b[0] < 3 and b[1] < 6 and b[2] > 96 and b[3] > 92:
            print("   ok      %s covers the screen (no border to measure)" % kind)
            continue
        tot_extra += 1
        print("   OFF     %s l %5.1f t %5.1f r %5.1f b %5.1f on no measured window"
              % (kind, b[0], b[1], b[2], b[3]))
print()
print("windows matched %d, MISSED %d, boxes on no window %d" % (tot_ok, tot_miss, tot_extra))
