"""Do the frame-picking tests give the SAME answer on quarter-size greys?"""
import sys, time, importlib.util
import numpy as np, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
sp = importlib.util.spec_from_file_location("cap", r"G:\AI\Ethereal\ui-extractor\_probe\capture_raw.py")
cap = importlib.util.module_from_spec(sp); sp.loader.exec_module(cap)
V = r"G:\Video\Move Memory Files Out of Claude Code Into Obsidian\Move Memory Files Out of Claude Code Into Obsidian (2160p_30fps_AV1-128kbit_AAC-English).mp4"
agree_sharp = agree_cut = 0; tries = 0
for ts in ("00:00:10", "00:01:40", "00:02:40", "00:03:20", "00:04:10"):
    frames = cap._ffmpeg_burst(V, ts, 1.5)
    if not frames: continue
    tries += 1
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    small = [cv2.resize(g, (g.shape[1]//4, g.shape[0]//4), interpolation=cv2.INTER_AREA) for g in grays]
    big_s = [cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]
    sml_s = [cv2.Laplacian(g, cv2.CV_64F).var() for g in small]
    pick_b, pick_s = int(np.argmax(big_s)), int(np.argmax(sml_s))
    mb = [float(np.mean(np.abs(a.astype(np.int16)-b.astype(np.int16)))) for a,b in zip(grays, grays[1:])]
    ms = [float(np.mean(np.abs(a.astype(np.int16)-b.astype(np.int16)))) for a,b in zip(small, small[1:])]
    cb = [i for i,m in enumerate(mb) if m >= cap.CUT_THRESHOLD]
    cs = [i for i,m in enumerate(ms) if m >= cap.CUT_THRESHOLD]
    stb = (max(mb) < cap.STILL_THRESHOLD) if mb else True
    sts = (max(ms) < cap.STILL_THRESHOLD) if ms else True
    agree_sharp += (pick_b == pick_s); agree_cut += (cb == cs and stb == sts)
    print("%s  sharpest frame: full %2d, quarter %2d %s | cuts %s/%s  still %s/%s %s"
          % (ts, pick_b, pick_s, "SAME" if pick_b==pick_s else "DIFFERENT",
             cb, cs, stb, sts, "" if (cb==cs and stb==sts) else "DIFFERENT"))
print("\nsharpest frame agreed %d of %d; cut and stillness agreed %d of %d" % (agree_sharp, tries, agree_cut, tries))
