import io, ast
p = "/home/trism/.claude/jobs/014c964f/tmp/replay/panes.py"
s = io.open(p, encoding="utf-8").read()

# 1. the import
old = "import overlay\nimport screenness\nimport machine"
new = "import overlay\nimport screenness\nimport shapes\nimport machine"
assert old in s, "import hunk"
s = s.replace(old, new, 1)

# 2. _borders measures the window's body
old = '''def _borders(work):
    """Columns holding a line that runs the full height of the window."""
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    k = np.ones((1, 41), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    cov = (cv2.max(lighter, darker) > 4).mean(axis=0)
    return [x for x, v in enumerate(cov) if v >= 0.75]'''
new = '''def _borders(work):
    """Columns holding a line that runs the full height of the window.

    The height counted is the window's BODY, not its title bar: the divider
    between a Finder window's sidebar and its list begins under the title
    bar and stops above the path bar, so measured against the whole crop it
    covers four fifths of it and was missed. Missing it reads the sidebar
    and the list as one thing, and a Finder window comes back as prose.
    """
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    k = np.ones((1, 41), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    ink = cv2.max(lighter, darker) > 4
    h = ink.shape[0]
    head, foot = int(0.10 * h), max(1, int(0.96 * h))
    body = ink[head:foot] if foot > head + 4 else ink
    return [x for x, v in enumerate(body.mean(axis=0)) if v >= 0.75]'''
assert old in s, "_borders hunk"
s = s.replace(old, new, 1)

# 3. _measured_windows, ahead of frame_regions
add = '''def _measured_windows(img):
    """Every window on this frame, from both ways of measuring one.

    A window is a rectangle with four drawn sides (overlay.py) - but a
    window pushed off the side of the screen has only three, and a window
    whose sides fade across its title bar is found starting below its own
    head. shapes.py measures those too. Missing a window is what makes the
    reader take two windows standing side by side as one pane, and read
    their two lists as one table with the wrong words in every row.
    """
    got = [tuple(int(round(v)) for v in r) for r in overlay.windows(img)]
    try:
        more = [tuple(int(round(v)) for v in r) for r in shapes.windows(img)]
    except Exception:
        more = []

    def inside(a, b):
        """How much of a stands within b."""
        w = min(a[2], b[2]) - max(a[0], b[0])
        h = min(a[3], b[3]) - max(a[1], b[1])
        if w <= 0 or h <= 0:
            return 0.0
        return (w * h) / max(1.0, (a[2] - a[0]) * (a[3] - a[1]))

    # Only whole WINDOWS are added, never the panes inside them: a window is
    # cut into its own panes below, and adding its list and its sidebar as
    # windows too cuts the same ground three times over. On one frame that
    # turned two windows into forty-nine and the read took four minutes.
    more.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
    top = []
    for box in more:
        if box[2] - box[0] < 8 or box[3] - box[1] < 8:
            continue
        if any(inside(box, k) > 0.85 for k in top):
            continue
        top.append(box)
    for box in top:
        if not any(inside(box, k) > 0.8 and inside(k, box) > 0.8 for k in got):
            got.append(box)
    return got


'''
anchor = "def frame_regions(img, engine=None):"
assert anchor in s, "anchor"
s = s.replace(anchor, add + anchor, 1)

# 4. frame_regions asks both finders
old = "    found = overlay.windows(img)\n    for x0, y0, x1, y1 in found:"
new = "    found = _measured_windows(img)\n    for x0, y0, x1, y1 in found:"
assert old in s, "frame_regions hunk"
s = s.replace(old, new, 1)

ast.parse(s)
io.open(p, "w", encoding="utf-8").write(s)
print("base restored:", len(s), "bytes")
