"""The names the note leaves cut short are not one problem. Split them."""
import re, collections
NOTE = r"G:\AI\Ethereal\ui-extractor\_probe\note-cards91.md"
s = open(NOTE, encoding="utf-8", errors="replace").read()
s = re.sub(r"<style.*?</style>|<script.*?</script>", " ", s, flags=re.S)
t = re.sub(r"<[^>]+>", "\n", s).replace("&nbsp;", " ")
cut = collections.Counter()
for line in t.splitlines():
    for tok in re.findall(r"[A-Za-z0-9._~$-]*(?:\.\.\.|\u2026)[A-Za-z0-9._~$-]*", line):
        if len(tok) > 6: cut[tok] += 1
SIZE = re.compile(r"\d\s*(KB|MB|GB|bytes)", re.I)
KIND = re.compile(r"(Markdo|Folder|Document|textfile|text\b|Applicat|PNGimage|JSON)", re.I)
PATH = re.compile(r"^-?Users-|^-Volumes-|/")
kinds = collections.Counter(); examples = collections.defaultdict(list)
for tok, n in cut.items():
    if PATH.search(tok):
        k = "a path bar, cut on screen (correct)"
    elif re.search(r"\.(md|json|py|sh|txt|png|yml|toml)$", tok, re.I):
        k = "a real file name, cut on screen"
    elif SIZE.search(tok) and KIND.search(tok):
        k = "two columns run together (size + kind)"
    elif SIZE.search(tok) or KIND.search(tok):
        k = "a size or kind word, welded to something"
    elif re.match(r"^\d", tok):
        k = "opens with a digit: a size or a numbered folder"
    else:
        k = "other"
    kinds[k] += n; examples[k].append(tok)
tot = sum(kinds.values())
print("%-42s %6s %7s" % ("what the cut-short thing actually is", "uses", "share"))
for k, v in kinds.most_common():
    print("%-42s %6d %6.0f%%" % (k, v, 100*v/tot))
    for e in sorted(examples[k])[:4]:
        print("        %s" % e[:66])
print("\ntotal cut-short uses: %d across %d distinct strings" % (tot, len(cut)))
