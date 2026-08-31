"""Of the names the note leaves cut short, how many could be completed from a
name the RECORD already read whole? That gap is the gate's headroom."""
import re, sys, collections, json
NOTE = r"G:\AI\Ethereal\ui-extractor\_probe\note-cards91.md"
REC  = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
def text_of(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    s = re.sub(r"<style.*?</style>|<script.*?</script>", " ", s, flags=re.S)
    return re.sub(r"<[^>]+>", "\n", s).replace("&nbsp;", " ")
def is_name(t):
    return (t.startswith(".") or "_" in t or re.search(r"[A-Za-z0-9]\.[A-Za-z0-9]", t)) \
           and not re.fullmatch(r"[\d.]+s?", t)
note = text_of(NOTE)
cut = collections.Counter()
for line in note.splitlines():
    for t in re.findall(r"[A-Za-z0-9._~$-]*(?:\.\.\.|\u2026)[A-Za-z0-9._~$-]*", line):
        if len(t) > 6: cut[t] += 1
# every whole name anywhere in the RECORD, not just the note
whole = set()
for l in open(REC, encoding="utf-8", errors="replace"):
    for t in re.findall(r"[A-Za-z0-9._~$-]{6,}", l):
        if "..." in t or "\u2026" in t: continue
        if is_name(t): whole.add(t)
print("note leaves %d distinct names cut short; the record holds %d distinct whole names" % (len(cut), len(whole)))
def head_tail(t):
    m = re.split(r"\.\.\.|\u2026", t)
    return m[0], (m[-1] if len(m) > 1 else "")
mend = []; nomend = []
for t in cut:
    h, tl = head_tail(t)
    if len(h) < 3: continue
    hits = [w for w in whole if w.startswith(h) and (not tl or w.endswith(tl)) and len(w) > len(t)]
    (mend if hits else nomend).append((t, hits[:2]))
print("\nCOULD have been completed from a whole reading in the record: %d of %d" % (len(mend), len(mend)+len(nomend)))
for t, h in sorted(mend)[:18]:
    print("   %-42s -> %s" % (t[:42], h[0][:52]))
print("\nno whole reading anywhere to complete them from: %d" % len(nomend))
for t, _ in sorted(nomend)[:12]:
    print("   %s" % t[:60])
