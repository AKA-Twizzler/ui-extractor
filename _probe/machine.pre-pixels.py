#!/usr/bin/env python3
"""Where this machine keeps the things this build needs.

The build runs on Windows, because that is where its data is. A frame of
video is read off G: and a picture is written back to G: thousands of times
in a run, and from Linux every one of those crossings is answered by a
Windows process -- so Linux work on a Windows drive slows Windows itself
rather than only WSL. The machine record has the measurement: one drive walk
over F: from the Linux side put the load average at 43 while the processors
sat half idle with seventeen processes blocked on I/O.

It still has to run from Linux, because that is where the agent lives and
because a person may reasonably run it either way. So the paths in the code
stay written the one way -- the Linux way, `/mnt/g/Images` -- and this module
is the single place that says what that means on the machine underneath.
Nowhere else asks which platform it is on.

  the drives     `/mnt/g/...` is `G:\\...` on Windows, and the vault's NAS is
                 the same SMB share either way: `//192.168.1.170/Public`
                 mounted at `/mnt/nas` from Linux, `\\\\192.168.1.170\\Public`
                 by name from Windows.

  the programs   ffmpeg and ffprobe are on the path on both. tesseract is on
                 the path on Linux and is a portable copy beside the build on
                 Windows, extracted rather than installed so that it needed
                 nobody's password.

  the memory     how much a reader enlarges a picture before reading it, and
                 what that costs to hold. It is one rule shared by every
                 reader rather than each one's own business, so it lives here
                 for the same reason the drives do -- see enlarge().
"""
import os
import re
import shutil
import sys

NAS = r"\\192.168.1.170\Public"     # the same share /mnt/nas is mounted from

# Windows writes its console in cp1252 unless told otherwise, and this build
# exists to reproduce a screen exactly -- the terminal fixture alone carries a
# warning triangle, a bullet and a tick, and the file trees are drawn with
# chevrons and guide bars. In cp1252 the run does not print them wrongly, it
# stops with an encoder error partway through the answer. Set here rather than
# in each entry point because forgetting it in one of them is silent until the
# one frame that needs it.
if os.name == "nt":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

# where the portable copy was put, next to the build rather than inside it:
# it is a tool several builds may want, and it is not ours to keep in git
_PORTABLE_TESSERACT = r"G:\AI\Ethereal\tools\Tesseract-OCR\tesseract.exe"

_MOUNT = re.compile(r"^/mnt/([a-z])(/.*)?$")


def here(path):
    """A path written the Linux way, as THIS machine reads it.

    Left alone on Linux, and left alone on Windows when it is already a
    Windows path -- so a video named on the command line works whichever way
    it was typed.
    """
    if os.name != "nt" or not isinstance(path, str):
        return path
    if path.startswith("/mnt/nas"):
        return NAS + path[len("/mnt/nas"):].replace("/", "\\")
    m = _MOUNT.match(path)
    if m:
        return m.group(1).upper() + ":" + (m.group(2) or "/").replace("/", "\\")
    return path


# How big a picture a reader may be handed at once. No limit by default; the
# name is kept only so the experiment below can be repeated from the command
# line without editing anything -- READ_PIXELS=24000000 python pipeline.py ...
READ_PIXELS = int(os.environ.get("READ_PIXELS", 0))


def enlarge(img, times=3):
    """Enlarge a picture for reading. The one home for the rule, uncapped.

    Every reader enlarges what it is given, because at native size a stroke is
    two or three pixels and a measurement taken on whole pixels cannot
    separate bold from body. Eight places said "times three" in their own
    words; they now say it here once, so that when the enlargement is worked
    out properly there is one place for the answer to land.

    The enlargements MULTIPLY, and that is the real cost. The splitter widens
    a narrow pane toward 1400 pixels, up to five times, so a 278x2160 strip
    arrives at the reader already 1390x10800 and the reader's three lands on
    top of it: 135 million pixels, handed to two engines and written to disk
    twice. Measured on one 4K frame, as peak working set:

        modules and engines loaded             0.11 GB
        capture, the burst of 44 frames        1.97 GB
        the panel reader                       5.42 GB
        the column reader                      6.45 GB

    and 11.23 GB over a whole run, on a machine with 34 GB that is also
    running other work. Nothing leaks -- the held figure stays near 135 MB the
    whole way through -- but a peak is what fails an allocation, and this build
    has already lost a run to ONNX's 'bad allocation' at exactly this size.

    A pixel ceiling was tried here and is NOT kept, because it turned out to
    be a tolerance rather than a measurement. At 24 million it saved real
    memory -- the panel reader 3.45 GB to 0.54 GB, the whole frame 6.45 GB to
    2.95 GB -- and cost two readings: a Finder window came back with 4 rows
    where it holds 16, and the Clock's lap table was not read at all. Raised
    to 64 million to clear those, it stopped cutting anything that had been
    proven and started cutting by accident. Of the 503 panes on disk, what
    they ask for at three times runs

        ... 59.5  60.0  61.0  62.5  63.0  64.0 | 64.4  66.5  67.2  68.8 ...

    with no gap anywhere near the line. 49 of the 503 would be read at two
    times and their next-door neighbours at three, for a difference no frame
    could tell you about. A threshold with no gap beneath it is a bug waiting
    for its frame, so there is no threshold here.

    Asking the picture was tried too, and it is refused with harder numbers.
    "Measure the stroke and enlarge until it can be measured" sounds like the
    principled form -- measured across the 505 stored panes it would read 446
    at one, 20 at two and 39 at three, and cut the pixels handed to the
    readers from 15,811 million to 2,542 million. Built and run against the
    suite, TEN of forty stages fail. The premise is wrong: a stroke a
    MEASUREMENT can resolve at six pixels is nowhere near what the second
    engine needs to read. With the enlargement cut, tesseract's confirmations
    collapse -- a real note fell from 0.84 backed to 0.31, another to 0.55
    against a gate of 0.67 -- the terminal lattice loses its pitch (0.28 of a
    pitch off a whole multiple, refused), the chat log loses its colours, the
    Finder table drops to 4 rows of 16. Every reader is calibrated to the
    world times-three produces, and the engines keep gaining accuracy well
    past the point where a stroke is merely measurable.

    Two refusals now close this family: a ceiling by pixels and a ceiling by
    stroke both trade readings for memory, and readings are the standard. The
    peak stands as measured above, as the price of the accuracy bar. If the
    peak must ever come down, the honest route is engineering the PEAK --
    reading the enlarged picture in bands, or freeing this copy before the
    second engine takes the file -- never handing the readers fewer pixels.
    """
    import cv2
    h, w = img.shape[:2]
    if h < 1 or w < 1:
        return img
    times = max(1, int(times))
    if READ_PIXELS:
        times = max(1, min(times, int((READ_PIXELS / float(h * w)) ** 0.5)))
    if times <= 1:
        return img
    return cv2.resize(img, (w * times, h * times),
                      interpolation=cv2.INTER_LANCZOS4)


def _tesseract():
    """The tesseract binary, or the reason there isn't one.

    An environment variable wins, so a different copy can be tried without
    editing anything. Otherwise the path, which is the Linux answer. The
    portable copy is last, because a properly installed one should win.
    """
    named = os.environ.get("TESSERACT")
    if named and os.path.exists(named):
        return named
    found = shutil.which("tesseract")
    if found:
        return found
    if os.path.exists(_PORTABLE_TESSERACT):
        return _PORTABLE_TESSERACT
    return None


TESSERACT = _tesseract()


def tesseract_or_refuse():
    """The binary, or an exception saying plainly what is missing.

    Nothing here guesses at text without an engine, so a reader that cannot
    find one stops rather than returning a thinner answer that looks whole.
    """
    if TESSERACT is None:
        raise RuntimeError(
            "tesseract was not found: not in TESSERACT, not on the path, and "
            f"not at {_PORTABLE_TESSERACT}. Two engines are the method here, "
            "so one engine is not a lesser answer -- it is a different one.")
    return TESSERACT


if __name__ == "__main__":
    print(f"platform     {os.name}")
    print(f"tesseract    {TESSERACT}")
    print(f"ffmpeg       {shutil.which('ffmpeg')}")
    print(f"ffprobe      {shutil.which('ffprobe')}")
    for p in ("/mnt/g/Images", "/mnt/g/Video", "/mnt/nas/obsidian-vault"):
        there = here(p)
        print(f"{p:24} -> {there}   {'ok' if os.path.isdir(there) else 'MISSING'}")

def write_once(path, img, source=None):
    """Write a picture only if it is not already on disk and current.

    THE SAME 3x ENLARGEMENT WAS WRITTEN UP TO FOUR TIMES PER PANE. columns,
    console_reader, chat_reader and note_reader each derive the same
    `<pane>_3x.png` from the same pane and each wrote it, and the file is a
    genuine shared artifact -- note_reader.tess_text_for reads it back and
    checks.py tests for it -- so it cannot simply go. It only had to be written
    ONCE. Measured on one 2280x1340 pane: enlarging costs 0.12 s and writing
    the 6840x4020 PNG costs 3.42 s, so three of the four writes were three and
    a half seconds each of the identical bytes.

    Current means: the file exists and is no older than the picture it came
    from, so a pane re-cut by a later run is never read as its predecessor.
    """
    import os as _os
    try:
        if _os.path.exists(path) and _os.path.getsize(path) > 0:
            if source is None or not _os.path.exists(source):
                return path
            if _os.path.getmtime(path) >= _os.path.getmtime(source):
                return path
    except OSError:
        pass
    import cv2 as _cv2
    _cv2.imwrite(path, img)
    return path
