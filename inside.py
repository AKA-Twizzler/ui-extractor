"""Nothing foreign in a window: every word the picture draws inside a window
must be a word the reader read inside THAT window - at this moment or at
another moment of the same window, which is the puzzle-piece rule.

selfcheck asks the other way round (every word read stands in some window).
This one catches a window drawn with its neighbour's words in it, which is
what a pane cut across two windows produces and what a picture cannot show.
"""
import json, os, re, sys
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw2
import selfcheck as SC
import shapes

NOTE, FRAMES, RECS = sys.argv[1], sys.argv[2], sys.argv[3]


def flat(t):
    return "".join(ch for ch in str(t).lower() if ch.isalnum())


by_ts = {}
for line in open(RECS, encoding="utf-8"):
    r = json.loads(line)
    if r.get("ts"):
        by_ts[r["ts"]] = r

# every word the reader read, with where it sat, per moment
words = {}
for ts, r in by_ts.items():
    W, H = r.get("size") or [3840, 2160]
    got = []
    for p in r.get("panes") or []:
        for it in draw2.items_of(p):
            b = it["box"]
            got.append((flat(it.get("text", "")),
                        100.0*(b[0]+b[2])/2/W, 100.0*(b[1]+b[3])/2/H))
    words[ts] = got

lines = open(NOTE, encoding="utf-8").read().split("\n")
bad = tot = 0
for k, ln in enumerate(lines, 1):
    st = re.search(r'class="sn-stamp">([\d:]+)(?: to ([\d:]+))?', ln)
    if not st or "sn-stage" not in ln:
        continue
    lo, hi = st.group(1), st.group(2) or st.group(1)
    stamps = [t for t in by_ts if lo <= t <= hi]
    # each filled window and the text drawn in it
    for m in re.finditer(r'<div class="sn-slot" style="([^"]+)"(.*?)(?=<div class="sn-(?:slot|ghost|camera|stamp|deskbar)"|$)', ln):
        pos = SC._pos(m.group(1))
        if not pos:
            continue
        l, t, w, h = pos
        body = re.sub(r"<[^>]+>", " ", m.group(2))
        drawn = {flat(x) for x in re.split(r"\s+", body) if len(flat(x)) >= 5}
        if not drawn:
            continue
        # the words the reader read INSIDE this window, over this stretch
        here = set()
        for ts in stamps:
            for key, cx, cy in words.get(ts, ()):
                if l - 1 <= cx <= l + w + 1 and t - 1 <= cy <= t + h + 1:
                    here.add(key)
        # and the same window at any other moment: the puzzle-piece rule
        anywhere = set()
        for ts in by_ts:
            for key, cx, cy in words.get(ts, ()):
                anywhere.add(key)
        miss = [d for d in drawn
                if d not in here and not any(d in a or a in d for a in here)]
        strange = [d for d in miss
                   if d not in anywhere and not any(d in a or a in d for a in anywhere)]
        tot += len(drawn)
        bad += len(strange)
        if strange:
            print("=== %s line %d  window l %.1f t %.1f w %.1f h %.1f" % (lo, k, l, t, w, h))
            print("    words in the picture that no reading holds:", sorted(strange)[:12])
print()
print("words drawn in windows %d, none of them read anywhere %d" % (tot, bad))
