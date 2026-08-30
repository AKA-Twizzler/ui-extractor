import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import bigwin, shapes
from PIL import Image
path = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-04-00.png"
print("bigwin.big_windows(00-04-00):", bigwin.big_windows(path))
print("shapes.windows(00-04-00):", shapes.windows(path))
path2 = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-04-10.png"
print("bigwin.big_windows(00-04-10):", bigwin.big_windows(path2))
print("shapes.windows(00-04-10):", shapes.windows(path2))
im = Image.open(path).convert("L")
W, H = im.size
print("frame size", W, H)
# brightness along row y=300 (inside the Obsidian title bar area) x=380..620, and along column x=600 y=120..300
row = [im.getpixel((x, 300)) for x in range(380, 640, 4)]
print("row y=300 x=380..640 step4:", row)
col = [im.getpixel((600, y)) for y in range(120, 320, 4)]
print("col x=600 y=120..320 step4:", col)
# tree row pitch at 00:04:00 vs 00:04:10: mean brightness per row inside the tree pane, look for text rows
def text_rows(img, x0, x1, y0, y1):
    rows = []
    for y in range(y0, y1):
        v = sum(img.getpixel((x, y)) for x in range(x0, x1, 8)) / len(range(x0, x1, 8))
        rows.append(v)
    return rows
r1 = text_rows(im, 700, 1500, 450, 1000)
peaks = [450 + i for i in range(1, len(r1) - 1) if r1[i] > 70 and r1[i] >= r1[i-1] and r1[i] > r1[i+1]]
print("00-04-00 bright row peaks (tree text) y:", peaks[:40])
im2 = Image.open(path2).convert("L")
r2 = text_rows(im2, 100, 560, 100, 700)
peaks2 = [100 + i for i in range(1, len(r2) - 1) if r2[i] > 70 and r2[i] >= r2[i-1] and r2[i] > r2[i+1]]
print("00-04-10 bright row peaks (tree text) y:", peaks2[:40])
