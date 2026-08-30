import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, checks, panes
for key, stamp in (("jarvis", "00:01:30"), ("jarvis", "00:02:00"),
                   ("skills", "00:01:00")):
    img = cv2.imread(checks.frame(key, stamp))
    print(f"\n=== {key} {stamp}  frame {img.shape[1]}x{img.shape[0]}")
    boxes = panes.frame_regions(img, engine=checks.engine())
    for i, b in enumerate(boxes):
        print(f"   r{i:<2} {b}  w={b[2]-b[0]:<5} h={b[3]-b[1]}")
    print(f"   windows: {panes.overlay.windows(img)}")
