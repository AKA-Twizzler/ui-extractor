import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, time
import screenness
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    img = cv2.imread(p)
    print(f"\n{os.path.basename(p)}  native {img.shape[1]}x{img.shape[0]}")
    for width in (1280, 1600, 1920, 2560, img.shape[1]):
        if width > img.shape[1]:
            continue
        s = width / img.shape[1]
        small = cv2.resize(img, (width, int(img.shape[0] * s)),
                           interpolation=cv2.INTER_AREA)
        t = time.time()
        res, _ = eng(small)
        n = len(res) if res else 0
        ok = screenness.rows_aligned(res) if res else False
        print(f"   {width:5d}px  boxes {n:4d}  rows_aligned {ok}  "
              f"{time.time()-t:.1f}s")
