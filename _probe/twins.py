"""Two rows in ONE Finder list that are the same file drawn twice.

A list cannot hold two files of one name, so an exact repeat is a fault the
note can find in itself. A near-repeat is the same fault wearing a misread,
and the pairs it turns up say which letter confusions are worth folding --
evidence, rather than a list of confusions somebody thought of.
"""
import re, sys, difflib, collections

NOTE = sys.argv[1] if len(sys.argv) > 1 else "_probe/note-cards103.md"
text = open(NOTE, encoding="utf-8").read()

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())

tables = re.findall(r'<table class="sn-list[^"]*">(.*?)</table>', text, re.S)
exact = near = 0
confusions = collections.Counter()
for t in tables:
    rows = re.findall(r"(<tr[^>]*>.*?</tr>)", t, re.S)
    def texts(r):
        return [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
    # THE NAME COLUMN IS NAMED, and it is not always the first: a window the
    # screen cuts on the left shows Size and Kind alone, and comparing those
    # turns every "55 bytes" into a duplicate of every other.
    head = next((texts(r) for r in rows if "sn-head" in r), [])
    ni = next((i for i, h in enumerate(head) if h.lower().startswith("name")), None)
    if ni is None:
        continue
    names = []
    for r in rows:
        if "sn-head" in r:
            continue
        cells = texts(r)
        if len(cells) <= ni:
            continue
        nm = cells[ni]
        if nm:
            names.append(nm)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            x, y = norm(a), norm(b)
            if not x or not y:
                continue
            if x == y:
                exact += 1
                print("  EXACT  %r  twice" % a)
            elif (min(len(x), len(y)) >= 3
                  and difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.80):
                near += 1
                print("  NEAR   %-40r %r" % (a, b))
                sm = difflib.SequenceMatcher(None, x, y, autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag != "equal":
                        confusions[(x[i1:i2], y[j1:j2])] += 1
print("\n%d exact repeats, %d near repeats, over %d lists" % (exact, near, len(tables)))
if confusions:
    print("the letter swaps behind the near repeats:")
    for (a, b), n in confusions.most_common(12):
        print("   %-10r -> %-10r  x%d" % (a, b, n))
