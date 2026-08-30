import sys, os, itertools
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3
LONG = '-Users-jaredrhodenizer-Documents-jarvis-demo'
def mk():
    return {
     "home":   ['Macintosh HD','Users','jaredrhodenizer'],
     "claude": ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts'],
     "jarvis": ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts',LONG],
     "projects":['Macintosh HD','Users','jaredrhodenizer','.claude','projerts'],
     "memory": ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts',LONG,'memory','MEMORY.md'],
     "vault":  ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo'],
     "compA":  ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Company A (Info Product)'],
     "dev":    ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Company A (Info Product)','Dev'],
     "assets": ['Macintosh HD','Users','jaredrhodenizer','Documents','vault-demo','02 Co','Assets'],
    }
BAD = ['Macintosh HD','Users','jaredrhodenizer','.claude','projerts','Users','jaredrhodenizer','memory','MEMORY.md']
def run(order, label):
    d = mk()
    paths = [d[k] for k in order]
    for i in range(len(paths)):
        paths[i] = draw3.mend_path(paths[i], [p for j,p in enumerate(paths) if j != i])
    mi = order.index("memory")
    hit = paths[mi] == BAD
    print("%-52s memory -> %s%s" % (label, paths[mi], "   <<< MATCHES CARD" if hit else ""))
    if hit:
        for k,p in zip(order,paths): print("      %-9s %s" % (k,p))
    return hit
run(["home","claude","jarvis","projects","memory"], "grp1 (home,claude,jarvis,projects,memory)")
run(["home","claude","jarvis","projects","memory","compA","dev","assets"], "grp1 + compA/dev/assets")
run(list(mk().keys()), "all nine, note order")
# every ordering of the five, to see if order matters
seen=False
for perm in itertools.permutations(["home","claude","jarvis","projects","memory"]):
    d=mk(); paths=[d[k] for k in perm]
    for i in range(len(paths)):
        paths[i]=draw3.mend_path(paths[i],[p for j,p in enumerate(paths) if j!=i])
    if paths[perm.index("memory")]==BAD:
        print("PERM REPRO", perm); seen=True; break
print("perm repro:", seen)
