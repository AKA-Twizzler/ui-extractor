import sys, os, itertools
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3
MEM = ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts',
       '-Users-jaredrhodenizer-Documents-jarvis-demo','memory','MEMORY.md']
CAND = {
 "home":   ['Macintosh HD','Users','jaredrhodenizer'],
 "vault":  ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo'],
 "claude": ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts'],
 "jarvis": ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts','-Users-jaredrhodenizer-Documents-jarvis-demo'],
 "compA":  ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Company A (Info Product)'],
 "dev":    ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Company A (Info Product)','Dev'],
 "assets": ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Co','Assets'],
}
BAD = ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts','Users','jaredrhodenizer','memory','MEMORY.md']
print("single others:")
for k,v in CAND.items():
    r = draw3.mend_path(list(MEM), [v])
    print("  %-7s -> %s%s" % (k, r, "   <<< MATCHES CARD" if r == BAD else ""))
print()
print("align_crumbs alone:")
for k,v in CAND.items():
    print("  %-7s -> %s" % (k, draw3.align_crumbs(list(MEM), v)))
print()
print("crumb_same('-Users-...-jarvis-demo', x):")
for x in ['Users','jaredrhodenizer','Documents','vault-demo','memory','Macintosh HD','.claude','projerts','02 Co']:
    print("   %-18r %s" % (x, draw3.crumb_same('-Users-jaredrhodenizer-Documents-jarvis-demo', x)))
print()
print("pairs / triples that reproduce:")
keys=list(CAND)
for n in (2,3,4):
    for combo in itertools.permutations(keys, n):
        r = draw3.mend_path(list(MEM), [CAND[c] for c in combo])
        if r == BAD:
            print("  REPRO", combo, "->", r)
            break
    else:
        continue
    break
