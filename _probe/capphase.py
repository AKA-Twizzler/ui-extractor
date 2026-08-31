"""What capture_moment spends after the frames are in hand."""
import sys, time, importlib.util
import numpy as np, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
sp = importlib.util.spec_from_file_location("cap", r"G:\AI\Ethereal\ui-extractor\_probe\capture_raw.py")
cap = importlib.util.module_from_spec(sp); sp.loader.exec_module(cap)
V = r"G:\Video\Move Memory Files Out of Claude Code Into Obsidian\Move Memory Files Out of Claude Code Into Obsidian (2160p_30fps_AV1-128kbit_AAC-English).mp4"
t = time.perf_counter(); frames = cap._ffmpeg_burst(V, "00:02:40", 1.5); t_burst = time.perf_counter()-t
print("frames %d %s" % (len(frames), frames[0].shape))
t = time.perf_counter(); grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]; t_gray = time.perf_counter()-t
t = time.perf_counter()
moves = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16)))) for a, b in zip(grays, grays[1:])]
t_moves = time.perf_counter()-t
t = time.perf_counter(); out = cap._median_stack(frames); t_med = time.perf_counter()-t
t = time.perf_counter(); sharp = [cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]; t_lap = time.perf_counter()-t
t = time.perf_counter(); cv2.imwrite(r"G:\AI\Ethereal\ui-extractor\_probe\capout.png", out, [cv2.IMWRITE_PNG_COMPRESSION, 3]); t_write = time.perf_counter()-t
# the same motion test on quarter-size greys
small = [cv2.resize(g, (g.shape[1]//4, g.shape[0]//4), interpolation=cv2.INTER_AREA) for g in grays]
t = time.perf_counter()
small = [cv2.resize(g, (g.shape[1]//4, g.shape[0]//4), interpolation=cv2.INTER_AREA) for g in grays]
m2 = [float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16)))) for a, b in zip(small, small[1:])]
t_small = time.perf_counter()-t
print("\n%-34s %7s" % ("", "seconds"))
for n, v in (("the burst (decode + pipe)", t_burst), ("to grey, 44 frames", t_gray),
             ("motion, full size", t_moves), ("median stack", t_med),
             ("sharpness (Laplacian)", t_lap), ("write the one frame", t_write),
             ("motion, quarter size (incl. resize)", t_small)):
    print("%-34s %7.2f" % (n, v))
print("\nmotion readings agree: %s   (full max %.3f, quarter max %.3f)"
      % (all(abs(a-b) < 0.5 for a, b in zip(moves, m2)), max(moves), max(m2)))
