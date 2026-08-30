import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, capture
rng = np.random.default_rng(7)
for n in (3, 4, 7, 12, 44, 45):
    frames = [rng.integers(0, 256, (600, 400, 3), dtype=np.uint8) for _ in range(n)]
    old = np.median(np.stack(frames).astype(np.float32), axis=0).astype(np.uint8)
    new = capture._median_stack(frames)
    same = np.array_equal(old, new)
    print(f"n={n:3d}  identical: {same}"
          + ("" if same else f"   max diff {int(np.abs(old.astype(int)-new.astype(int)).max())}"))
