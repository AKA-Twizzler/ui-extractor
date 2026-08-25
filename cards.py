"""The 'every window, rebuilt to read' half of the note, on the vault's own
style sheet, shot so it can be looked at."""
import re, subprocess, sys
from PIL import Image
import numpy as np
SRC = sys.argv[1]
md = open(SRC, encoding="utf-8").read()
css = open("/mnt/nas/obsidian-vault/.obsidian/snippets/screen-notes.css", encoding="utf-8").read()
i = md.find("## Every window, rebuilt to read")
sect = md[i:] if i >= 0 else md
sect = sect.split("\n## Moment by moment")[0]
body = []
for ln in sect.split("\n"):
    if ln.startswith("<div"):
        body.append(ln)
    elif ln.startswith("#"):
        body.append("<h3>" + ln.lstrip("# ") + "</h3>")
    elif ln.strip():
        body.append("<p>" + ln + "</p>")
head = ("<!doctype html><html><head><meta charset='utf-8'><style>\n"
        ":root { --background-primary:#1e1e1e; --background-primary-alt:#262626; --background-secondary:#222; "
        "--background-modifier-border:#3a3a3a; --text-muted:#9a9a9a; --text-normal:#dcddde; "
        "--interactive-accent:#7f6df2; --font-interface: Segoe UI, sans-serif; }\n"
        "body { background:#1e1e1e; color:#dcddde; font-family: Segoe UI, sans-serif; max-width: 1000px; "
        "margin: 20px auto; font-size: 15px; } h3 { margin: 26px 0 6px; }\n" + css + "\n</style></head><body>\n")
open("cards.html","w",encoding="utf-8").write(head + "\n".join(body) + "\n</body></html>")
subprocess.run(["cp","cards.html","/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/look/cards.html"])
subprocess.run(["/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
                "--headless","--disable-gpu","--hide-scrollbars","--window-size=1100,26000",
                "--screenshot=G:\\AI\\Ethereal\\ui-extractor\\_probe\\look\\cards.png",
                "file:///G:/AI/Ethereal/ui-extractor/_probe/look/cards.html"], stderr=subprocess.DEVNULL)
im = Image.open("/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/look/cards.png")
a = np.array(im.convert("L")); rows = np.where((a != 30).any(axis=1))[0]
h = rows.max() + 20; n = (h + 1499)//1500
for k in range(n):
    im.crop((0,k*1500,1100,min(h,(k+1)*1500))).save(f"/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/look/card_{k}.png")
print(n, h)
