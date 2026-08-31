"""Where the skim thinks a webcam frame is interface, and what else is true there."""
import sys, glob, os
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

def grids(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    ties = sc.tie_map(bgr).astype(np.float32)
    # a STEP edge: a neighbour differing by a lot. Text and window borders make
    # these; a lens and its compression make ramps.
    step = np.zeros(g.shape, np.float32)
    step[:, :-1] = np.abs(np.diff(g, axis=1)) > 32
    h, w = g.shape
    r, c = sc.GRID
    T = np.zeros(sc.GRID, np.float32); S = np.zeros(sc.GRID, np.float32)
    B = np.zeros(sc.GRID, np.float32)
    for i in range(r):
        y0, y1 = i * h // r, (i + 1) * h // r
        for j in range(c):
            x0, x1 = j * w // c, (j + 1) * w // c
            T[i, j] = ties[y0:y1, x0:x1].mean()
            S[i, j] = step[y0:y1, x0:x1].mean()
            B[i, j] = g[y0:y1, x0:x1].mean()
    return T, S, B

for f in sorted(glob.glob(sys.argv[1])):
    bgr = cv2.imread(f)
    T, S, B = grids(bgr)
    print("\n== %s   skim says %s (%.0f%% interface)" %
          (os.path.basename(f), sc.verdict(bgr)[0], sc.screen_fraction(sc.to_working_size(bgr))[0]*100))
    for name, G, fmt in (("ties", T, "%5.2f"), ("steps", S, "%5.3f"), ("bright", B, "%5.0f")):
        print("  %-7s" % name + "  ".join("".join(fmt % v for v in row) for row in [G[0]]))
        for row in G[1:]:
            print("  %-7s" % "" + "".join(fmt % v for v in row))
