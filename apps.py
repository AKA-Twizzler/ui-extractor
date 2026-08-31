"""What programs a video actually contains, named from the menu bar.

WHY THIS EXISTS. A pane is offered to every reader in turn -- tree, terminal,
columns, chat, document -- and at most one claims it. Measured over one video:
those five are 58% of all reader time, and the terminal reader alone is 16% and
claimed NOTHING, because there is no terminal anywhere in that video. The chat
reader is another 7% and claimed nothing for the same reason. A quarter of the
reading was spent proving the absence of things a glance would have ruled out.

THE GLANCE IS THE MENU BAR. macOS writes the frontmost program's name at the
left of it, and that strip costs 0.03 to 0.12 seconds to read against the 12 to
30 seconds a pane costs. It is not on every frame -- a zoomed recording often
crops it away, and only 12 of this video's 29 moments show one -- and that is
enough, because the question is what is in the VIDEO, not what is in a moment.
One sighting of Terminal anywhere means the terminal reader earns its place;
none anywhere means it never runs.

WHAT THIS DELIBERATELY DOES NOT DO. It does not decide what a PANE is. That is
the pane's own business and the readers do it well. It only says which readers
could possibly be needed at all, which is a different question and one nothing
in the tool asked before.
"""

import difflib
import os
import re

# The bar strip: the top of the screen, and only the left third, where the
# program's name and its menus sit. The right end carries the clock and the
# status icons, which are never a program name.
BAR_HEIGHT = 0.028
BAR_WIDTH = 0.30

# The words that follow a program's name in every macOS menu bar. The name is
# whatever stands BEFORE the first of these, so the list only has to be long
# enough to find the boundary.
MENU_WORDS = ("file", "edit", "view", "window", "help", "format", "insert",
              "go", "shell", "terminal", "history", "bookmarks", "profiles",
              "develop", "tools", "actions", "selection", "run")

# Programs whose presence changes which readers are worth running. The value is
# the reader kinds that program can produce.
KNOWN = {
    "Finder": ("list", "tree"),
    "Obsidian": ("document", "tree"),
    "Terminal": ("terminal",),
    "iTerm": ("terminal",),
    "iTerm2": ("terminal",),
    "Warp": ("terminal",),
    "Ghostty": ("terminal",),
    "Alacritty": ("terminal",),
    "Kitty": ("terminal",),
    "Code": ("document", "tree", "terminal"),
    "Cursor": ("document", "tree", "terminal"),
    "Xcode": ("document", "tree", "terminal"),
    "Chrome": ("document",),
    "Safari": ("document",),
    "Firefox": ("document",),
    "Arc": ("document",),
    "Slack": ("chat",),
    "Discord": ("chat",),
    "Messages": ("chat",),
    "Telegram": ("chat",),
    "Zoom": ("chat",),
    "Notes": ("document",),
    "TextEdit": ("document",),
    "Preview": ("document",),
    "Mail": ("document",),
    "Pages": ("document",),
    "Numbers": ("list",),
    "Keynote": ("document",),
}
_FOLD = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())
_KNOWN_FOLD = [(k, _FOLD(k)) for k in KNOWN]


def name_of(reading):
    """The program named at the left of a menu-bar reading, or None.

    The engines mangle it -- "obaidian" for Obsidian, "Findet" for Finder --
    so the name is matched against the known list by similarity rather than
    equality. The bar's own menu words mark where the name ends; anything
    that matches no program is returned as None rather than guessed at,
    because a wrong program name would switch off a reader that was needed.
    """
    s = re.sub(r"[^A-Za-z ]+", " ", reading or "")
    if not s.strip():
        return None
    # the name runs up to the first menu word, wherever that begins
    low = s.lower()
    cut = len(s)
    for w in MENU_WORDS:
        for m in re.finditer(w, low):
            i = m.start()
            if 2 < i < cut:
                cut = i
    head = _FOLD(s[:cut])
    if len(head) < 3:
        return None
    # EACH NAME IS TESTED AGAINST THE HEAD'S OWN LENGTH, not the whole run.
    # The menu words are misread too -- "Fle" for File, "Edt" for Edit -- so
    # the boundary above often falls a word or two late and the run comes back
    # as "obaidianfleedt". Comparing that whole string to "obsidian" scores
    # far too low; comparing its first nine characters scores 0.82 and is
    # right. A program's name opens the bar, so a prefix is the honest test.
    best, score = None, 0.0
    for k, kf in _KNOWN_FOLD:
        r = difflib.SequenceMatcher(None, head[:len(kf) + 1], kf).ratio()
        if r > score:
            best, score = k, r
    return best if score >= 0.72 else None


def app_of_frame(path, engine=None, ocr=None):
    """The program frontmost in this frame, or None where no bar is on it."""
    import cv2
    im = cv2.imread(path)
    if im is None:
        return None
    h, w = im.shape[:2]
    # A PICTURE THIS SHORT IS ALREADY THE STRIP. scan_video crops the bar out
    # of the video itself and hands over sixty rows; taking 2.8% of THAT is one
    # pixel, and the first version of this read zero bars from the video while
    # reading ten from the same moments' full frames.
    strip = im if h <= 200 else im[0:max(8, int(h * BAR_HEIGHT)), :]
    bar = strip[:, 0:max(40, int(w * BAR_WIDTH))]
    if bar.size == 0:
        return None
    import numpy as np
    # IS THERE A BAR AT ALL, asked of the WHOLE strip rather than the left of
    # it. The clock and the status icons sit at the right end and are ink like
    # any other; a bar whose left third happens to be quiet is still a bar, and
    # testing only the left third found one frame of twelve.
    med = float(np.median(strip))
    if float((np.abs(strip.astype(np.int16) - med) > 40).mean()) < 0.005:
        return None                       # no writing up there: no bar on this frame
    if ocr is None:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe"))
        import pixfirst
        ocr = lambda a: pixfirst.ocr(a, 2.0)
    got = ocr(bar[:, :, ::-1].copy())
    words = "".join(w_[4] for w_ in sorted(got, key=lambda w_: w_[0]))
    return name_of(words)


def in_video(frame_paths, ocr=None):
    """Every program the video shows, and the reader kinds they can produce.

    Returns (apps, kinds, bars_read). `bars_read` is how many frames actually
    carried a bar, and a caller must check it before trusting an ABSENCE: no
    bars read means nothing was learned, not that nothing is there.
    """
    apps, bars = {}, 0
    for p in frame_paths:
        a = app_of_frame(p, ocr=ocr)
        if a:
            bars += 1
            apps[a] = apps.get(a, 0) + 1
    kinds = set()
    for a in apps:
        kinds.update(KNOWN.get(a, ()))
    return apps, kinds, bars


def scan_video(video, timestamps, workdir=None, ocr=None):
    """The programs a video contains, from the menu bar of each chosen moment.

    IT DECODES THE STRIP AND NOTHING ELSE. Seeking to a moment and decoding
    only the top sixty rows costs about 0.33 s where a whole frame costs 12 to
    15; all 29 moments of one video come to 9.5 s, and the reading on top of
    that is under 4. That is the price of knowing, before a single pane is
    read, that a quarter of the reader time can be skipped.

    It runs BEFORE the moments are read rather than alongside them, and the
    reason is safety rather than tidiness: a terminal that appears once at the
    end of a video would be missed by anything that learns as it goes, and it
    would be missed silently.
    """
    import subprocess
    import tempfile
    own = workdir is None
    workdir = workdir or tempfile.mkdtemp(prefix="apps-")
    seen = {}
    bars = 0
    try:
        for ts in timestamps:
            t = ts if isinstance(ts, (int, float)) else _to_seconds(ts)
            out = os.path.join(workdir, "bar_%06d.png" % int(t))
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % float(t), "-i", video,
                 "-frames:v", "1", "-vf", "crop=in_w:60:0:0", out],
                capture_output=True)
            if r.returncode != 0 or not os.path.exists(out):
                continue
            a = app_of_frame(out, ocr=ocr)
            if a:
                bars += 1
                seen[a] = seen.get(a, 0) + 1
            try:
                os.unlink(out)
            except OSError:
                pass
    finally:
        if own:
            try:
                os.rmdir(workdir)
            except OSError:
                pass
    kinds = set()
    for a in seen:
        kinds.update(KNOWN.get(a, ()))
    return seen, kinds, bars


def _to_seconds(ts):
    parts = [float(p) for p in str(ts).split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


# How many bars must be read before an ABSENCE is believed. Below this nothing
# was learned: a video whose recording crops the menu bar away teaches nothing
# about what is in it, and must run every reader as before.
ENOUGH_BARS = 3


def readers_to_skip(kinds, bars):
    """Which readers this video cannot need. Empty where nothing was learned."""
    if bars < ENOUGH_BARS:
        return set()
    skip = set()
    if "terminal" not in kinds:
        skip.add("terminal")
    if "chat" not in kinds:
        skip.add("chat")
    return skip
