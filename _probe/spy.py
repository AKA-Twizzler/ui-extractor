import sys, os
sys.path.insert(0, r"G:\\AI\\Ethereal\\ui-extractor")
import cv2, numpy as np, machine, overlay
real = machine.enlarge
def spy(img, times=3):
    h, w = img.shape[:2]
    afford = int((machine.READ_PIXELS / float(h*w)) ** 0.5)
    got = max(1, min(int(times), afford))
    print(f"  enlarge {w}x{h}  asked {times}x  afforded {afford}x  used {got}x  -> {w*got*h*got/1e6:.1f} Mpx", flush=True)
    return real(img, times)
machine.enlarge = spy
overlay.machine.enlarge = spy
import capture
path, how = capture.capture_moment(sys.argv[1], sys.argv[2], r"G:\\Images\\_probe")
img = cv2.imread(path)
print("frame", img.shape, how, flush=True)
overlay.read_overlays(path, r"G:\\Images\\_probe")
