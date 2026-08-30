"""Can the program's name be read off the menu bar, and off nothing else?

macOS puts the front program's name second on the menu bar, after the Apple
glyph. Candidate rule: OCR the top band; a menu bar is MANY short words on
one row; the leftmost word is the name. Frames that have no menu bar must
refuse. Measure the shape on known frames before building anything.
"""
import sys
import cv2

sys.path.insert(0, ".")

FRAMES = [
    ("works desktop (Finder)",
     "G:/Images/How Claude Code Actually Works/00-07-29.png"),
    ("jarvis desktop",
     "G:/Images/My AI Jarvis Makes Money. Here's How/00-02-00.png"),
    ("obsidian full screen",
     "G:/Images/How To Set Up Claude Code With Obsidian/00-02-09.png"),
    ("install (Finder over Obsidian)",
     "G:/Images/Install Claude Code and-or the AI Memory Vault/00-07-14.png"),
    ("stjude stream (no bar)",
     "G:/Images/Jarvis and Jaredrhod Raise Money for St. Jude's Children's "
     "Hospital - Live Replay 8-1-26/02-12-59.png"),
    ("skills slide (no bar)",
     "G:/Images/How To Make Your Own AI Skills/00-01-30.png"),
    ("beginners talking head (no bar)",
     "G:/Images/Claude Code For Beginners; Start Here/00-05-28.png"),
    ("memfiles desktop (Finder)",
     "G:/Images/Move Memory Files Out of Claude Code Into Obsidian/"
     "00-00-00.png"),
]

from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

for tag, path in FRAMES:
    img = cv2.imread(path)
    if img is None:
        print(f"{tag}: MISSING")
        continue
    h, w = img.shape[:2]
    band = img[0:max(24, int(h * 0.03))]
    big = cv2.resize(band, (band.shape[1] * 2, band.shape[0] * 2),
                     interpolation=cv2.INTER_LANCZOS4)
    res, _ = eng(big)
    words = []
    for b, t, conf in (res or []):
        x0 = min(p[0] for p in b) / 2
        y0 = min(p[1] for p in b) / 2
        y1 = max(p[1] for p in b) / 2
        words.append((x0, y0, y1, t.strip(), conf))
    words.sort()
    show = " | ".join(f"{t}@{int(x)}" for x, _, _, t, _ in words[:10])
    print(f"{tag}\n   band {band.shape[1]}x{band.shape[0]}: "
          f"{len(words)} words: {show}")
