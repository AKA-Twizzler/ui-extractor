import sys, os, subprocess, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np

def peak():
    r = subprocess.run(["wmic", "process", "where", f"processid={os.getpid()}",
                        "get", "PeakWorkingSetSize"],
                       capture_output=True, text=True)
    for line in r.stdout.split():
        if line.isdigit():
            return int(line) * 1024 / 1e9
    return -1.0

def now():
    r = subprocess.run(["wmic", "process", "where", f"processid={os.getpid()}",
                        "get", "WorkingSetSize"], capture_output=True, text=True)
    for line in r.stdout.split():
        if line.isdigit():
            return int(line) * 1024 / 1e9
    return -1.0

def say(what):
    print(f"  {what:<44} held {now():5.2f} GB   peak so far {peak():5.2f} GB",
          flush=True)

import capture, screenness, panes, tree_reader, console_reader, columns
import chat_reader, note_reader, overlay, verify_names
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
say("engines and modules loaded")

video = sys.argv[1]; ts = sys.argv[2]
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mem")
os.makedirs(out, exist_ok=True)
path, how = capture.capture_moment(video, ts, out)
gc.collect(); say(f"capture_moment ({how[:26]})")

img = cv2.imread(path)
say(f"frame read {img.shape[1]}x{img.shape[0]}")
regions = screenness.ui_regions(img, eng)
gc.collect(); say(f"screenness ({len(regions)} regions)")

pans = overlay.read_overlays(path, eng)
gc.collect(); say(f"overlay.read_overlays ({len(pans['panels'])} panels)")

looks = overlay.frames_across(video, capture._to_seconds(ts),
                              workdir=os.path.join(out, "_looks"))
st = overlay.standing_text(looks, engine=eng)
gc.collect(); say(f"standing_text ({len(st)} admitted)")

boxes = panes.frame_regions(img, engine=eng)
gc.collect(); say(f"panes.frame_regions ({len(boxes)} panes)")

for i, box in enumerate(boxes):
    p = os.path.join(out, f"m_pane{i}.png")
    if panes.write_box(img, box, p) is None:
        continue
    h, w = cv2.imread(p).shape[:2]
    for name, fn in (("tree_reader", lambda: tree_reader.read_tree(p)),
                     ("console_reader", lambda: console_reader.read_console(p)),
                     ("columns", lambda: columns.read_list(p)),
                     ("chat_reader", lambda: chat_reader.read_chat(p, engine=eng)),
                     ("note_reader", lambda: note_reader.read_note(p))):
        try:
            fn()
        except Exception as why:
            print(f"      {name} raised {type(why).__name__}", flush=True)
        gc.collect(); say(f"pane {i} ({w}x{h}) after {name}")
