"""The third reader: Windows' own OCR (Windows.Media.Ocr), reached through
one PowerShell process per batch (winocr.ps1 beside this file). It is
already on this PC with English installed, costs no download and no disk,
reads a whole 4K frame in a quarter of a second, and its misses are not the
other two engines' misses (it drops and misreads; it does not invent). It
is the third vote in pixels-first reading, never the only reader.

    read_words(rgb, scale=2.0) -> [(x0, y0, x1, y1, text)]   in the crop's own pixels
    read_images([path, ...])   -> the engine's own result per image (boxes in image pixels)

Readings are cached by the image's bytes under pixfirst-cache/winocr, so a
frame read once is never handed to the engine again."""
import hashlib, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(HERE, "winocr.ps1")
CACHE = os.path.join(HERE, "pixfirst-cache", "winocr")


def available():
    return sys.platform == "win32" and os.path.exists(PS1)


def read_images(paths, timeout=300):
    """The engine's result for each image path (Windows paths), in order."""
    if not paths:
        return []
    fd, lst = tempfile.mkstemp(suffix=".json", prefix="winocr-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump([os.path.abspath(p) for p in paths], f)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1, lst],
                           capture_output=True, timeout=timeout)
    finally:
        os.remove(lst)
    out = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError("winocr: %s" % r.stderr.decode("utf-8", "replace")[-400:])
    res = json.loads(out)
    return res if isinstance(res, list) else [res]


def _words_of(result):
    out = []
    for line in result.get("lines") or []:
        for w in line.get("words") or []:
            out.append((float(w["x"]), float(w["y"]), float(w["x"]) + float(w["w"]), float(w["y"]) + float(w["h"]), str(w["t"])))
    return out


def read_words(rgb, scale=2.0):
    """The words in a crop (an RGB array), enlarged `scale` times for the
    engine, as (x0, y0, x1, y1, text) in the crop's own pixels."""
    im = Image.fromarray(np.asarray(rgb))
    if scale != 1.0:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    fd, png = tempfile.mkstemp(suffix=".png", prefix="winocr-")
    os.close(fd)
    im.save(png)
    with open(png, "rb") as f:
        key = hashlib.sha1(f.read()).hexdigest()
    os.makedirs(CACHE, exist_ok=True)
    cached = os.path.join(CACHE, key + ".json")
    try:
        if os.path.exists(cached):
            with open(cached, encoding="utf-8") as f:
                result = json.load(f)
        else:
            result = read_images([png])[0]
            with open(cached, "w", encoding="utf-8") as f:
                json.dump(result, f)
    finally:
        os.remove(png)
    return [(x0 / scale, y0 / scale, x1 / scale, y1 / scale, t) for x0, y0, x1, y1, t in _words_of(result)]


if __name__ == "__main__":
    for res in read_images(sys.argv[1:]):
        print(res["path"], res["w"], "x", res["h"], res["ms"], "ms", len(res["lines"]), "lines")
        for line in res["lines"]:
            ws = line["words"]
            print("  [%d,%d] %s" % (ws[0]["x"] if ws else 0, ws[0]["y"] if ws else 0, line["text"]))
