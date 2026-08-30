import sys
sys.path.insert(0, r"G:\\AI\\Ethereal\\ui-extractor")
import cv2, numpy as np, machine
print("READ_PIXELS =", machine.READ_PIXELS)
rng = np.random.default_rng(7)
same = 0
for (h, w) in [(37,53),(2160,3840),(1104,6339),(1390,10800),(3219,2160),(1,9),(9,1)]:
    img = rng.integers(0,256,(h,w,3),dtype=np.uint8)
    for t in (2,3,4):
        old = cv2.resize(img,(w*t,h*t),interpolation=cv2.INTER_LANCZOS4)
        new = machine.enlarge(img,t)
        ok = old.shape==new.shape and np.array_equal(old,new)
        same += ok
        if not ok: print("  DIFFERS", h, w, t, old.shape, new.shape)
    del img
print(f"  {same} of 21 enlargements bit-identical to the call they replaced")
