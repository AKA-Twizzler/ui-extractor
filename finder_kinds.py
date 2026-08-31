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
    # carried over from draw3's own list, so nothing it used to know is lost
    "Plain Text", "Text Document", "Unix executable", "JavaScript",
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

def _brackets(head, tail):
    """The kinds a cut reading can be: it opens with `head` and what follows
    runs on into `tail`. The TAIL MAY ITSELF BE CUT -- a narrow column gives
    "Markdo...text fi" -- so the tail need only appear after the head, not
    finish the word. The closed vocabulary is what makes that safe: only one
    kind opens with "markdo", so a partial tail still names it exactly."""
    if not head:
        return []
    out = []
    for k, kf in _KFOLD:
        if not kf.startswith(head) or len(kf) <= len(head):
            continue
        rest = kf[len(head):]
        if not tail or rest.endswith(tail) or (len(tail) >= 2 and tail in rest):
            out.append(k)
    return out


def _match(rest):
    """The one kind this reading can be, or None where it is not one or is two."""
    f = _FOLD(rest)
    if not f:
        return None
    if ELL.search(rest):
        head, tail = [_FOLD(x) for x in ELL.split(rest, 1)]
        hits = _brackets(head, tail)
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


_INTEXT = re.compile(r"([A-Za-z]{3,})(?:\.\.\.|\u2026)([A-Za-z][A-Za-z ]{1,20}?)(?=[^A-Za-z ]|$)")

def spell_in_text(s):
    """Every cut kind inside a line, spelled whole. Returns (line, how many).

    The strict form: a run of letters, an ellipsis, then a run of letters that
    together bracket exactly ONE kind. "Markdo...text file" is one kind and
    nothing else, so it is safe; a cut FILE NAME brackets nothing and is left
    exactly as the screen showed it.
    """
    if not s or ("..." not in s and "\u2026" not in s):
        return s, 0
    n = 0
    def one(m):
        nonlocal n
        head, tail = _FOLD(m.group(1)), _FOLD(m.group(2))
        hits = _brackets(head, tail)
        if len(hits) == 1:
            n += 1
            # the tail run swallows the spaces that padded a table cell; give
            # them back, or the note's columns lose their alignment
            pad = len(m.group(2)) - len(m.group(2).rstrip())
            return hits[0] + (" " * pad)
        return m.group(0)
    return _INTEXT.sub(one, s), n
