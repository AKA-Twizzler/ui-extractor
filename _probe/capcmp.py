"""Does the raw-pipe capture produce the SAME finished frame, and how fast?"""
import sys, time, importlib.util, tempfile, os
import numpy as np, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
old = load("cap_old", r"G:\AI\Ethereal\ui-extractor\capture.py")
new = load("cap_new", r"G:\AI\Ethereal\ui-extractor\_probe\capture_raw.py")
V = r"G:\Video\Move Memory Files Out of Claude Code Into Obsidian\Move Memory Files Out of Claude Code Into Obsidian (2160p_30fps_AV1-128kbit_AAC-English).mp4"
for ts in sys.argv[1:] or ["00:02:40"]:
    res = {}
    for tag, mod in (("PNGs", old), ("pipe", new)):
        d = tempfile.mkdtemp(dir=r"G:\AI\Ethereal\ui-extractor\_probe")
        t = time.perf_counter()
        p, how = mod.capture_moment(V, ts, d)
        secs = time.perf_counter() - t
        res[tag] = (cv2.imread(p, cv2.IMREAD_COLOR), how, secs)
        for f in os.listdir(d): os.unlink(os.path.join(d, f))
        os.rmdir(d)
    a, b = res["PNGs"][0], res["pipe"][0]
    ok = a is not None and b is not None and a.shape == b.shape and np.array_equal(a, b)
    print("%s  the old way %5.1f s  |  the pipe %5.1f s  |  %.1fx faster" %
          (ts, res["PNGs"][2], res["pipe"][2], res["PNGs"][2]/max(0.01, res["pipe"][2])))
    print("      frame identical: %s     how: %r / %r" % (ok, res["PNGs"][1], res["pipe"][1]))
    if not ok and a is not None and b is not None and a.shape == b.shape:
        print("      biggest pixel gap %d" % int(np.abs(a.astype(int)-b.astype(int)).max()))
