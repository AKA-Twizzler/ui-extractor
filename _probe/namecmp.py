"""The names two builds of the note carry, set side by side."""
import re, sys, collections
def names(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    txt = re.sub(r"<[^>]+>", "\n", s)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    out = collections.Counter()
    for line in txt.splitlines():
        for tok in re.findall(r"[A-Za-z0-9._~$-]{4,}", line):
            # a name: carries a dot inside it, or opens with one
            if tok.startswith(".") or re.search(r"[A-Za-z0-9]\.[A-Za-z0-9]", tok):
                if re.fullmatch(r"[\d.]+s?", tok) or re.fullmatch(r"\d+\.\d+", tok):
                    continue
                if True:
                    out[tok] += 1
    return out
a, b = names(sys.argv[1]), names(sys.argv[2])
print("build A %s: %d distinct names" % (sys.argv[1].split("/")[-1][:40], len(a)))
print("build B %s: %d distinct names" % (sys.argv[2].split("/")[-1][:40], len(b)))
only_a = sorted(set(a) - set(b)); only_b = sorted(set(b) - set(a))
print("\nin BOTH: %d" % len(set(a) & set(b)))
print("\nonly in the NEW build (%d):" % len(only_a))
for n in only_a[:40]: print("   %s" % n)
print("\nonly in the build 85 reference (%d):" % len(only_b))
for n in only_b[:40]: print("   %s" % n)
