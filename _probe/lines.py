import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import shapes, cv2
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
g, W, H = shapes._grey(img)
h, w = g.shape
k = W / float(w)
verts, hors = shapes._sides(g, int(shapes.RUN * h), int(shapes.RUN * w))
verts, hors = shapes._thin(verts), shapes._thin(hors)
print("scale k", round(k, 3), "work", w, h)
def near(lines, pos, tol):
    return [(round(p*k), round(a*k), round(b*k)) for p, a, b in lines if abs(p*k - pos) <= tol]
for x in (184, 388, 1748, 1760, 1811, 1828):
    print("VERT near x=%d:" % x, near(verts, x, 14))
for y in (472, 494, 1128, 1140, 1148):
    print("HOR  near y=%d:" % y, near(hors, y, 14))
