import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import checks, panes, overlay, shapes
cases = [("works", "00:01:52"), ("obsidian", "00:07:30"), ("obsidian", "00:06:00"),
         ("memfiles", "00:00:00"), ("jarvis", "00:02:00"), ("skills", "00:01:00"),
         ("works", "00:07:29"), ("post", "00:00:30")]
for key, stamp in cases:
    img = cv2.imread(checks.frame(key, stamp))
    h, w = img.shape[:2]
    boxes = [tuple(int(v) for v in r[:4]) for r in overlay.windows(img)]
    boxes += [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
    print("===", key, stamp)
    for b in boxes:
        share = 100.0 * (b[2]-b[0]) * (b[3]-b[1]) / (w*h)
        print("   %-28s %5.1f%%  buttons: %s" % (str(b), share,
                                                 panes._has_buttons(img, b)))
