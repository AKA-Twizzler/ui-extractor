import sys, os, re, difflib
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw2, draw as old
from draw3 import fold, flat, overlap, rect_at, screens, frag_owner
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
all_states = draw3.build_states(moments)
bar_at, clock_at, strip_at = draw3.desktop_bar(moments)
H0 = (moments[0].get("size") or [0, 2160])[1]
for st in all_states:
    draw3.strip_furniture(st, strip_at)
    if draw3.bar_title(st, H0):
        st.title = None
def _doc_fold(st):
    d = st.main_doc()
    return fold("".join(flat(t) for t, _ in d.lines)) if d and d.lines else ""
_named = [(st, _doc_fold(st)) for st in all_states if draw3.is_real_window(st.name)]
_named = [(st, t) for st, t in _named if len(t) >= 40]
for c in all_states:
    if c.name != "The rest of the screen": continue
    ct = _doc_fold(c)
    if len(ct) < 12: continue
    for w, wt in _named:
        sm = difflib.SequenceMatcher(None, ct, wt, autojunk=False)
        longest = sm.find_longest_match(0, len(ct), 0, len(wt)).size
        frac = sum(b.size for b in sm.get_matching_blocks()) / max(1, len(ct))
        if longest >= 40 or (len(ct) >= 12 and frac >= 0.6):
            c.name = w.name; break
states = [st for st in all_states if st.window_html() and not st.fragment()]
real = [st for st in states if draw3.is_real_window(st.name)]
shown = real
spans = [s for s in screens(states, moments) if any(st in shown for st in s["states"])]
print("SPANS:")
for s in spans:
    print("  t0=%s ts=%s states=%s" % (s["t0"], s["ts"], [(st.name.split()[1], st.times[0]) for st in s["states"]]))
# ---- word_boxes / fit_map replicated from draw3.note() lines 4926-5010
def word_boxes(m):
    seen = {}
    for p in m.get("panes") or []:
        for it in draw2.items_of(p):
            key = fold(flat(it["text"]))
            if len(key) >= 5:
                seen.setdefault(key, []).append(it["box"])
    return {k: v[0] for k, v in seen.items() if len(v) == 1}
words_of = {m["ts"]: word_boxes(m) for m in moments}
base_ts = max(words_of, key=lambda t: len(words_of[t]))
base_words = words_of[base_ts]
Wf, Hf = (moments[0].get("size") or [1920, 1080])[:2]
print("base_ts =", base_ts, "with", len(base_words), "unique word boxes; frame", Wf, Hf)
def med(vals):
    vals = sorted(vals); return vals[len(vals) // 2]
def fit_map(ts_list, verbose=False):
    mine = {}
    for t in ts_list:
        for key, b in (words_of.get(t) or {}).items():
            mine.setdefault(key, b)
    exact = [(base_words[key], q) for key, q in mine.items() if key in base_words]
    cuts = []
    for key, q in mine.items():
        if key in base_words or len(key) < 10: continue
        cands = [bk for bk in base_words if len(bk) >= 10 and (bk.endswith(key) or key.endswith(bk))]
        if len(cands) == 1:
            cuts.append((base_words[cands[0]], q, "tail")); continue
        cands = [bk for bk in base_words if len(bk) >= 10 and (bk.startswith(key) or key.startswith(bk))]
        if len(cands) == 1:
            cuts.append((base_words[cands[0]], q, "head"))
    kv = [(q[2] - q[0]) / max(1.0, p[2] - p[0]) for p, q in exact if p[2] - p[0] >= 8]
    kv += [(q[3] - q[1]) / max(1.0, p[3] - p[1]) for p, q in exact if p[3] - p[1] >= 10]
    kv += [(q[3] - q[1]) / max(1.0, p[3] - p[1]) for p, q, _ in cuts if p[3] - p[1] >= 10]
    if verbose:
        print("   fit_map(%s): exact=%d cuts=%d kv=%s" % (ts_list, len(exact), len(cuts), [round(x, 2) for x in sorted(kv)]))
    if len(kv) < 3: return None
    k = med(kv)
    if not 0.4 <= k <= 4.0: return None
    xs = [(p[0], q[0]) for p, q in exact] + [(p[2], q[2]) for p, q in exact]
    xs += [(p[2], q[2]) if side == "tail" else (p[0], q[0]) for p, q, side in cuts]
    ys = [(p[1], q[1]) for p, q in exact] + [(p[1], q[1]) for p, q, _ in cuts]
    for _ in range(2):
        dx = med([qx - k * px for px, qx in xs]); dy = med([qy - k * py for py, qy in ys])
        keep_x = [(px, qx) for px, qx in xs if abs(k * px + dx - qx) < 0.02 * Wf]
        keep_y = [(py, qy) for py, qy in ys if abs(k * py + dy - qy) < 0.02 * Hf]
        if len(keep_x) < 2 or len(keep_y) < 2: return None
        done = len(keep_x) == len(xs) and len(keep_y) == len(ys)
        xs, ys = keep_x, keep_y
        if done: break
    return (k, dx, dy)
def onto(T, box):
    k, dx, dy = T; return [k * box[0] + dx, k * box[1] + dy, k * box[2] + dx, k * box[3] + dy]
def back(T, box):
    k, dx, dy = T; return [(box[0] - dx) / k, (box[1] - dy) / k, (box[2] - dx) / k, (box[3] - dy) / k]
span_T = {s["t0"]: fit_map(s["ts"], verbose=(s["t0"] in ("00:04:00", "00:04:10", "00:04:40"))) for s in spans}
print("span_T:")
for t0, T in span_T.items():
    print("   %s -> %s" % (t0, None if T is None else tuple(round(x, 3) for x in T)))
# ---- home_reads / home_at replicated (lines 5381-5475)
secs_of = {m["ts"]: m.get("secs", 0) for m in moments}
obs = [st for st in states if st.name == "The Obsidian window"]
for st in obs:
    print("=" * 90)
    print("Obsidian state", st.times, "measured", sorted(st.measured.keys()) if hasattr(st, "measured") else None)
    only = set(st.measured) & set(st.rects)
    outs = []
    for t, r in st.rects.items():
        if only and t not in only: continue
        if not r or r[2] <= r[0]: continue
        s_ = next((x for x in spans if t in x["ts"]), None)
        T = (span_T.get(s_["t0"]) if s_ else None) or fit_map([t])
        print("   rect@%s = %s  T=%s  back=%s" % (t, [round(x) for x in r], None if not T else tuple(round(x, 3) for x in T), [round(x) for x in back(T, r)] if T else None))
        if not T: continue
        outs.append((secs_of.get(t, 0), back(T, r), T[0]))
    if not outs: continue
    # home_at clusters
    def iou(a, b):
        w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
        if w <= 0 or h <= 0: return 0.0
        inter = w * h; au = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
        return inter / max(1.0, au)
    def home_at(t0):
        want = secs_of.get(t0, 0)
        clusters = []
        for mem in sorted(outs):
            r = mem[1]
            for c in clusters:
                u = c[0]
                near = sum(1 for i in range(4) if abs(r[i] - u[i]) < 0.03 * (Wf if i % 2 == 0 else Hf))
                if iou(r, u) > 0.5 or (near >= 2 and overlap(r, u) > 0.6):
                    c[0] = [min(u[0], r[0]), min(u[1], r[1]), max(u[2], r[2]), max(u[3], r[3])]; c[1].append(mem); break
            else:
                clusters.append([list(r), [mem]])
        merged = True
        while merged and len(clusters) > 1:
            merged = False
            for i in range(len(clusters)):
                for j in range(len(clusters)):
                    if i == j: continue
                    a, b = clusters[i][0], clusters[j][0]
                    small = min((a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1]))
                    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
                    if w > 0 and h > 0 and (w * h) / max(1.0, small) > 0.6:
                        clusters[i][0] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                        clusters[i][1].extend(clusters[j][1]); clusters.pop(j); merged = True; break
                if merged: break
        best = min(clusters, key=lambda c: min(abs(m[0] - want) for m in c[1]))
        take = best[1]
        return [min(m[1][0] for m in take), min(m[1][1] for m in take), max(m[1][2] for m in take), max(m[1][3] for m in take)], len(clusters), [m[0] for m in take]
    for t0 in st.times[:3]:
        hb, ncl, members = home_at(t0)
        s_ = next((x for x in spans if t0 in x["ts"]), None)
        T0 = span_T.get(s_["t0"]) if s_ else None
        print("   home_at(%s) = %s  (clusters=%d, members secs=%s)  T0=%s  onto(T0,hb)=%s" % (
            t0, [round(x) for x in hb], ncl, members, None if not T0 else tuple(round(x, 3) for x in T0),
            [round(x) for x in onto(T0, hb)] if T0 else None))
print()
print("FRAG_OWNER of the renamed states vs the real Obsidian state (shared-lines evidence):")
real_obs = [st for st in obs if "00:04:00" in st.times][0]
for st in obs:
    if st is real_obs: continue
    print("   state", st.times[0], "-> owner:", getattr(frag_owner(st, [real_obs] + [x for x in states if x.name == "The Finder window"]), "times", frag_owner(st, [real_obs])))
