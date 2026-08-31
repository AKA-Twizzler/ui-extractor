"""Candidate: ties say WHERE a surface is flat; step edges say whether anything
was DRAWN on it. A dark room is flat with nothing drawn."""
import os, sys, itertools
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc
from screenbench import report

STEP_JUMP = 32

def maps(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    ties = sc.tie_map(bgr).astype(np.float32)
    st = np.zeros(g.shape, np.float32)
    st[:, :-1] = np.abs(np.diff(g, axis=1)) > STEP_JUMP
    st[:-1, :] = np.maximum(st[:-1, :], (np.abs(np.diff(g, axis=0)) > STEP_JUMP))
    h, w = g.shape
    r, c = sc.GRID
    T = np.zeros(sc.GRID, np.float32); S = np.zeros(sc.GRID, np.float32)
    for i in range(r):
        y0, y1 = i * h // r, (i + 1) * h // r
        for j in range(c):
            x0, x1 = j * w // c, (j + 1) * w // c
            T[i, j] = ties[y0:y1, x0:x1].mean()
            S[i, j] = st[y0:y1, x0:x1].mean()
    return T, S

def spread(S):
    """The most ink in this cell or any cell touching it."""
    return cv2.dilate(S, np.ones((3, 3), np.uint8))

def make(low, high):
    def call(bgr):
        T, S = maps(bgr)
        D = spread(S)
        cell = ((T >= sc.CELL_IS_SCREEN) & (D >= low)) | (S >= high)
        frac = float(cell.mean())
        return ("camera" if frac <= sc.SURE_CAMERA else
                "screen" if frac >= sc.SURE_SCREEN else "uncertain")
    return call

if __name__ == "__main__":
    for low, high in itertools.product([0.01, 0.02, 0.03, 0.05], [0.05, 0.08, 0.12, 1.1]):
        report("ink near >= %.2f  or dense >= %.2f" % (low, high), make(low, high))
