"""How glyph heights distribute inside real panes: is there a clean gap
between body text and what a person would call a title?  Sets LARGE."""
import glob
import sys

sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
from rapidocr_onnxruntime import RapidOCR

DIRS = [
    r"G:\Images\How Claude Code Actually Works",
    r"G:\Images\How To Make Your Own AI Skills",
    r"G:\Images\Turn Leads Into Customers With AI",
    r"G:\Images\How To Set Up Claude Code With Obsidian",
    r"G:\Images\Jarvis Visualizer with Claude Code",
    r"G:\Images\A Look Inside My Million Dollar AI Business",
]
eng = RapidOCR()
shown = 0
for d in DIRS:
    for path in sorted(glob.glob(d + r"\*_pane*.png"))[:8]:
        res, _ = eng(path)
        if not res or len(res) < 4:
            continue
        hs, ts = [], []
        for b, t, _ in res:
            hs.append(max(p[1] for p in b) - min(p[1] for p in b))
            ts.append(t)
        med = sorted(hs)[len(hs) // 2]
        if not med:
            continue
        ratios = sorted(((h / med, t) for h, t in zip(hs, ts)), reverse=True)
        top = "; ".join(f"{r:.2f} {t[:28]!r}" for r, t in ratios[:3])
        n2 = sum(1 for r, _ in ratios if r >= 2.0)
        n18 = sum(1 for r, _ in ratios if r >= 1.8)
        n15 = sum(1 for r, _ in ratios if r >= 1.5)
        print(f"{path.split(chr(92))[-2][:20]:<20} {path.split(chr(92))[-1][:28]:<28} "
              f"n={len(hs):<3} >=1.5:{n15} >=1.8:{n18} >=2.0:{n2}  {top}")
        shown += 1
print(f"{shown} panes measured")
print("PROBE-DONE")
