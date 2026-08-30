import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, capture, machine, screenness, spot
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
V = "Jarvis Visualizer with Claude Code"
mp4 = sorted(glob.glob(os.path.join(machine.here(f"/mnt/g/Video/{V}"), "*.mp4")))[0]
out = machine.here(f"/mnt/g/Images/{V}")
for ts in ("00:00:20", "00:00:50", "00:01:20", "00:01:50"):
    p, how = capture.capture_moment(mp4, ts, out)
    img = cv2.imread(p)
    regs = screenness.ui_regions(img, eng)
    share = sum(r["share"] for r in regs) * 100
    print(f"{ts}  {img.shape[1]}x{img.shape[0]}  interface {share:5.1f}%  "
          f"regions {len(regs)}")
