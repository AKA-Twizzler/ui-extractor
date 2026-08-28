import sys, os, json, re
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw2
from draw2 import *
recs=[json.loads(l) for l in open(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl",encoding="utf-8") if l.strip()]
m=next(r for r in recs if r.get("ts")=="00:01:10")
p=next(q for q in m["panes"] if q["pi"]==2)
items=items_of(p)
rows = reading_order(items, lambda it: it["box"])
head_row=None
for r in rows:
    heads=[h for it in r for h in split_heads(it["text"])]
    if len(heads)>=2 or (len(heads)==1 and heads[0]=="Name"): head_row=r; break
print("head_row",[it["text"] for it in head_row])
lone = len([h for it in head_row for h in split_heads(it["text"])]) == 1
rh = sorted(it["box"][3]-it["box"][1] for it in items)[len(items)//2] or 20
hy = (head_row[0]["box"][1]+head_row[0]["box"][3])/2
heads=[]
for it in sorted(head_row, key=lambda it: it["box"][0]):
    names=split_heads(it["text"]); 
    if len(names)==1: heads.append((names[0], it["box"][0], it["box"][2]))
print("heads",heads,"rh",rh,"hy",hy)
cols=[[x0,x1] for _,x0,x1 in heads]; x_lo=cols[0][0]; x_end=cols[-1][1]+3*rh
print("x_lo",x_lo,"x_end",x_end)
for ri,r in enumerate(rows):
    if r is head_row: continue
    cy=(r[0]["box"][1]+r[0]["box"][3])/2
    in_list=[it for it in r if it["box"][2] > x_lo-rh and it["box"][0] <= x_end and not (len(it["text"])>40 and it["text"].count(" ")>=5)]
    print("row",ri,[it["text"][:25] for it in r],"cy",cy,"above?",cy<hy-rh,"in_list",len(in_list),
          "crumby",all(crumb_like(it["text"]) for it in in_list) if in_list else None, "cy>hy+3rh", cy>hy+3*rh)
