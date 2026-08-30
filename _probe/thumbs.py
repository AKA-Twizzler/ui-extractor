import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
for p in sys.argv[1:]:
    i = cv2.imread(p)
    if i is None:
        print("no", p); continue
    s = cv2.resize(i, (900, int(i.shape[0]*900/i.shape[1])), interpolation=cv2.INTER_AREA)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "look_" +
                       os.path.basename(os.path.dirname(p))[:14].replace(" ","_") +
                       "_" + os.path.basename(p))
    cv2.imwrite(out, s)
    print(out)
