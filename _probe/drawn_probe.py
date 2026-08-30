import sys, os, glob
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2
import overlay, screenness, capture, machine

CASES = [
    ("the wallpapered desktop (wrong: Finder chrome called drawn-on)",
     r"G:\Video\How Claude Code Actually Works", "00:07:29"),
    ("the St Jude banner (right: a real overlay, must survive)",
     r"G:\Video\Jarvis Raises Money for St. Judes with Epic Performance - Live Replay July 31, 2026",
     "03:18:00"),
    ("the 8-1 banner",
     r"G:\Video\Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26",
     "01:15:59"),
    ("the Aug 03 banner (right: a real overlay, must survive)",
     r"G:\Video\Live August 03", "00:24:01"),
]

work = r"G:\Images\_probe_drawn"
os.makedirs(work, exist_ok=True)

from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

for name, folder, ts in CASES:
    mp4 = sorted(glob.glob(os.path.join(folder, "*.mp4")))
    if not mp4:
        print("--- %s\n    no mp4 in %s\n" % (name, folder))
        continue
    video = mp4[0]
    path, how = capture.capture_moment(video, ts, work)
    img = cv2.imread(path)
    regions = screenness.ui_regions(img, eng) or []
    share = sum(x["share"] for x in regions) * 100
    secs = capture._to_seconds(ts)
    frames = overlay.frames_across(video, secs, workdir=os.path.join(work, "_looks"))
    found = overlay.standing_text(frames, engine=eng)
    kept = overlay.floating(found, regions, img.shape[1], screenness.WORK_WIDTH)
    keptset = set(id(k) for k in kept)
    print("--- %s   (%s)" % (name, ts))
    print("    %d interface regions, share %.0f%%  (the old gate opens below 50%%)"
          % (len(regions), share))
    if not found:
        print("    nothing claimed as standing text at all")
    for f in found:
        mark = "kept   " if id(f) in keptset else "DROPPED"
        print("    %s  %-30s at %s" % (mark, repr(f["text"][:30]), f["box"]))
    print()
