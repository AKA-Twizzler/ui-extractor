"""Complete the last column of a Finder list from the kinds macOS actually writes."""
import re, difflib

# The kinds a Finder list writes in its Kind column. A closed set, published by
# the system rather than discovered from the pixels, which is the whole reason
# this works where the name lexicon cannot: a cut name may be anything, a cut
# kind is one of these.
KINDS = [
    "Folder", "Markdown text file", "Document", "Plain Text Document",
    "JSON", "Log File", "Application", "Alias", "PNG image", "JPEG image",
    "Shell Script", "Python Script", "Volume", "Disk Image", "Archive",
    "Zip archive", "PDF Document", "Text Edit Document", "Terminal Script",
]
_FOLD = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
_KFOLD = [(k, _FOLD(k)) for k in KINDS]
# "49 bytes", "1KB", and "49bytesN" where the engine leaves a stray capital.
# No \b after the unit: "bytesN" has no word boundary in it, which is exactly
# the case the stray appears in.
# NOT case-insensitive, deliberately: re.I would make the (?![a-z]) lookahead
# match an uppercase letter too, and the stray capital after "bytes" is exactly
# what that lookahead has to let through.
SIZE = re.compile(r"^\s*(\d[\d.,]*)\s*(KB|Kb|kB|kb|MB|GB|TB|bytes|Bytes|byte|Byte)(?![a-z])")
# A STRAY CAPITAL IS FOLLOWED BY A SPACE; A RUN-ON KIND IS NOT. "49bytesN Markdo"
# drops the N, "1KBMarkdo" keeps every letter of Markdown.
STRAY = re.compile(r"^([A-Z])(?=\s)")
ELL = re.compile(r"\.\.\.|\u2026")

def _match(rest):
    """The one kind this reading can be, or None where it is not one or is two."""
    f = _FOLD(rest)
    if not f:
        return None
    if ELL.search(rest):
        head, tail = [_FOLD(x) for x in ELL.split(rest, 1)]
        hits = [k for k, kf in _KFOLD
                if kf.startswith(head) and kf.endswith(tail) and len(kf) > len(head) + len(tail) - 1]
        if len(hits) == 1:
            return hits[0]
        return None
    exact = [k for k, kf in _KFOLD if kf == f]
    if exact:
        return exact[0]
    # a misread: same length give or take two, and close enough to only ONE kind
    near = [(difflib.SequenceMatcher(None, f, kf).ratio(), k)
            for k, kf in _KFOLD if abs(len(kf) - len(f)) <= 2]
    near.sort(reverse=True)
    if near and near[0][0] >= 0.72 and (len(near) == 1 or near[0][0] - near[1][0] >= 0.08):
        return near[0][1]
    return None

def finder_kind(s):
    """The reading with its kind spelled whole, or the reading unchanged.

    Returns (text, what_happened) where what_happened is "kind completed",
    "kind mended", "left alone" or "a date in the kind column" -- the last is
    not a kind at all and says the columns were split wrong on that row.
    """
    raw = (s or "").strip()
    if not raw:
        return raw, "left alone"
    if re.search(r"\b(AM|PM)\b|\d{1,2}:\d{2}", raw) and re.search(r"[A-Z][a-z]{2}\s*\d|Today|Yesterday", raw):
        return raw, "a date in the kind column"
    m = SIZE.match(raw)
    if m:
        # rebuilt from the groups, which drops the stray capital the engine
        # leaves after "bytes" ("49bytesN") without touching the unit's own
        # letters -- taking it off the END ate the B of KB
        size = "%s %s" % (m.group(1), m.group(2))
        rest = STRAY.sub("", raw[m.end():].lstrip()).strip()
    else:
        size, rest = "", raw
    if not rest:
        return raw, "left alone"
    kind = _match(rest)
    if not kind:
        return raw, "left alone"
    out = (size + " " + kind).strip() if size else kind
    return out, ("kind completed" if ELL.search(rest) else
                 ("left alone" if _FOLD(rest) == _FOLD(kind) else "kind mended"))
