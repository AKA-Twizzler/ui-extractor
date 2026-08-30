import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import shapes
img = cv2.imread(r"G:\Images\How To Set Up Claude Code With Obsidian\Images\00-02-09.png")
try:
    g = shapes._grey(img)
    print("_grey ok, shape", g.shape)
except Exception as e:
    print("_grey FAILED:", type(e).__name__, e)
print("_frame_area ->", shapes._frame_area(img, [[184.,792.,384.,986.]]))
print("windows ->", shapes.windows(img))
