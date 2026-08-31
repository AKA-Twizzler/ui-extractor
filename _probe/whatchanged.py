"""What is the CHEAP measure that says a screen became a different screen?

Today's is the mean grey change between two 320x180 thumbnails, over 4.0. On a
live stream that is tripped by the webcam alone, so every ten-second sample is
called a new screen: the five-hour replay came back as 1,981 screens and was
read as 1,594 moments -- while its own record shows only 84 distinct LAYOUTS.

The yardstick here is that record: for each sample, the arrangement of panes in
force at that time. A measure is good when it says CHANGED where the layout
changed and SAME where it did not. Every candidate runs on the thumbnails the
skim already cached, so this costs no decoding at all.
"""
import json, io, sys, collections
import numpy as np

Z = np.load("_probe/stjudes_thumbs.npz")
th, ts = Z["thumb"], Z["t"]
D = r"G:\Images\Jarvis Raises Money for St. Judes with Epic Performance - Live Replay July 31, 2026"

# the yardstick: what layout stood at each moment, carried forward to the samples
def hms(s):
    return "%02d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)
lay_at = {}
for line in io.open(D + "\\records.jsonl", encoding="utf-8"):
    d = json.loads(line)
    if d.get("kind") != "moment":
        continue
    W, H = (d.get("size") or [1280, 720])[:2]
    key = tuple(sorted((round(20.0 * b[0] / W), round(20.0 * b[1] / H),
                        round(20.0 * b[2] / W), round(20.0 * b[3] / H))
                       for b in [p.get("box") or [] for p in (d.get("panes") or [])] if len(b) == 4))
    h, m, s = (int(v) for v in d["ts"].split(":"))
    lay_at[h * 3600 + m * 60 + s] = key
times = sorted(lay_at)
truth = []
for t in ts:
    prev = [u for u in times if u <= t]
    truth.append(lay_at[prev[-1]] if prev else None)
changed_truth = [truth[i] is not None and truth[i - 1] is not None and truth[i] != truth[i - 1]
                 for i in range(1, len(truth))]
print("samples %d, layout changes in the record: %d" % (len(ts), sum(changed_truth)))

def edges(a):
    gx = np.abs(np.diff(a.astype(np.int16), axis=1))
    gy = np.abs(np.diff(a.astype(np.int16), axis=0))
    return gx, gy

def m_grey(a, b):
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))

def m_lines(a, b):
    """Where LONG straight edges stand. A window border runs most of a side;
    scrolling text and a moving camera make short edges everywhere."""
    def prof(x):
        gx, gy = edges(x)
        col = (gx > 24).mean(axis=0)          # a vertical edge, down the frame
        row = (gy > 24).mean(axis=1)          # a horizontal edge, across it
        return np.concatenate([col > 0.30, row > 0.30]).astype(np.float32)
    pa, pb = prof(a), prof(b)
    return float(np.mean(pa != pb))

def m_flat(a, b):
    """Where the picture is RENDERED rather than filmed: a camera puts noise on
    every pixel, so neighbours are almost never equal; a drawn interface paints
    flat runs. The map of flatness is the layout, and it is what screenness
    already counts."""
    def m(x):
        f = (np.diff(x.astype(np.int16), axis=1) == 0)
        h, w = f.shape
        blocks = f[:h // 12 * 12, :w // 16 * 16].reshape(h // 12, 12, w // 16, 16).mean(axis=(1, 3))
        return blocks > 0.55
    return float(np.mean(m(a) != m(b)))

for name, fn, thr in (("mean grey change (today's)", m_grey, 4.0),
                      ("long straight edges", m_lines, 0.05),
                      ("where the picture is drawn, not filmed", m_flat, 0.06)):
    said = [fn(th[i - 1], th[i]) > thr for i in range(1, len(th))]
    screens = 1 + sum(said)
    tp = sum(1 for s, t in zip(said, changed_truth) if s and t)
    fp = sum(1 for s, t in zip(said, changed_truth) if s and not t)
    fn_ = sum(1 for s, t in zip(said, changed_truth) if not s and t)
    print("%-40s -> %5d screens   caught %3d of %3d layout changes, cried wolf %4d times"
          % (name, screens, tp, tp + fn_, fp))
