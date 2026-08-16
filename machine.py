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
