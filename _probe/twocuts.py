"""Two different truncations of one name can complete each other.

A name cut in the MIDDLE keeps its head and its tail and loses the belly.
A name cut at the END keeps a longer head and loses the tail. Neither is whole,
but between them they often cover the whole string. This asks how many of the
record's cut names have a differently-cut sibling.
"""
import re, sys, collections, json
REC = sys.argv[1] if len(sys.argv) > 1 else \
    r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.pre-readfixes.jsonl"
ELL = re.compile(r"\.\.\.+|\u2026")
cut = collections.Counter()
for l in open(REC, encoding="utf-8", errors="replace"):
    for t in re.findall(r"[A-Za-z0-9._~$-]*(?:\.\.\.|\u2026)[A-Za-z0-9._~$-]*", l):
        if len(t) > 8 and ("_" in t or t.endswith(".md")):
            cut[t] += 1
def split(t):
    parts = ELL.split(t)
    return parts[0], (parts[-1] if len(parts) > 1 else "")
mid = {t: split(t) for t in cut if split(t)[1]}          # head...tail
end = {t: split(t)[0] for t in cut if not split(t)[1]}   # head...
print("cut names in the record: %d distinct (%d with a tail, %d without)"
      % (len(cut), len(mid), len(end)))
def splice(head, tail, least=3):
    """head + tail joined WHERE THEY OVERLAP, or None where they do not.

    The overlap is the proof. Two cuts of one name only complete each other
    when the longer head runs far enough to meet the tail: "..._to_th" and
    "he_page.md" share "h", and at three characters or more the join is the
    name. Where they do not meet, the belly is missing and anything spliced
    there is invented, so it is refused.
    """
    for n in range(min(len(head), len(tail)), least - 1, -1):
        if head[-n:] == tail[:n]:
            return head + tail[n:]
    return None

made = {}
for m, (h, tl) in mid.items():
    if len(h) < 5 or len(tl) < 3: continue
    for e, eh in end.items():
        if len(eh) <= len(h) or not eh.startswith(h):
            continue
        whole = splice(eh, tl)
        if whole and "." in whole and len(whole) > len(eh):
            made.setdefault(m, set()).add(whole)
print("\ncut names a differently-cut sibling could complete: %d" % len(made))
for m in sorted(made)[:14]:
    w = sorted(made[m], key=len)
    print("   %-40s + sibling -> %s" % (m[:40], w[0][:56]))
