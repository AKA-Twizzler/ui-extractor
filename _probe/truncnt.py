"""How many names each build leaves cut short, and how many it carries whole."""
import re, sys, collections
def pull(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    s = re.sub(r"<style.*?</style>|<script.*?</script>", " ", s, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", s).replace("&nbsp;", " ")
    cut = collections.Counter(); whole = collections.Counter()
    for line in t.splitlines():
        for tok in re.findall(r"[A-Za-z0-9._~$-]*(?:\.\.\.|\u2026)[A-Za-z0-9._~$-]*", line):
            if len(tok) > 4: cut[tok] += 1
        for tok in re.findall(r"[A-Za-z0-9._~$-]{6,}", line):
            if "..." in tok or "\u2026" in tok: continue
            if re.fullmatch(r"[\d.]+s?", tok): continue
            if tok.startswith(".") or re.search(r"[A-Za-z0-9]\.[A-Za-z0-9]", tok) or "_" in tok:
                whole[tok] += 1
    return cut, whole
for p in sys.argv[1:]:
    cut, whole = pull(p)
    print("%-46s  whole names %4d distinct (%4d uses) | CUT SHORT %3d distinct (%3d uses)"
          % (p.split("\\")[-1][:46], len(whole), sum(whole.values()), len(cut), sum(cut.values())))
if len(sys.argv) == 3:
    ca, wa = pull(sys.argv[1]); cb, wb = pull(sys.argv[2])
    print("\nnames the NEW build has whole and the reference does not (%d):" % len(set(wa)-set(wb)))
    for n in sorted(set(wa)-set(wb))[:25]: print("   %s" % n)
    print("\nnames the REFERENCE has whole and the new build does not (%d):" % len(set(wb)-set(wa)))
    for n in sorted(set(wb)-set(wa))[:25]: print("   %s" % n)
