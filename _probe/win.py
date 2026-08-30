import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, overlay, panes
img = cv2.imread(sys.argv[1])
print(f"frame {img.shape[1]}x{img.shape[0]}")
print("drawn windows found:")
for x0, y0, x1, y1 in overlay.windows(img):
    print(f"    x{x0}-{x1}  y{y0}-{y1}   ({x1-x0}x{y1-y0})")
print("panels found:")
for x0, y0, x1, y1 in overlay.panels(img):
    print(f"    x{x0}-{x1}  y{y0}-{y1}   ({x1-x0}x{y1-y0})")
