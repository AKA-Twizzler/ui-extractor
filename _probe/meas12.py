import sys, os, re, subprocess
sys.path.insert(0, "/mnt/g/AI/Ethereal/ui-extractor"); os.chdir("/mnt/g/AI/Ethereal/ui-extractor")
import compare
note = open("_probe/note-nomax.md", encoding="utf-8").read()
cards = [l for l in note.splitlines() if l.startswith('<div class="sn-window sn-obsidian')]
css = open(compare.CSS_PATH, encoding="utf-8").read()
out = "/mnt/g/AI/Ethereal/ui-extractor/_probe/wmeas"
JS = ("<script>window.addEventListener('load',function(){var w=document.querySelector('.sn-window');"
      "var t=document.querySelector('.sn-tree');var longest=0;"
      "if(t){t.querySelectorAll('div').forEach(function(d){if(d.scrollWidth>longest)longest=d.scrollWidth;});}"
      "var d=document.createElement('div');d.id='R';d.textContent='card='+w.offsetWidth"
      "+' tree='+(t?t.offsetWidth:-1)+' longestRow='+longest+' cut='+(t&&longest>t.clientWidth?'YES':'no');"
      "document.body.appendChild(d);});</script>")
for i, card in enumerate(cards):
    row = []
    for cw in (900, 1600):
        body = ("<div class='markdown-preview-view screen-note' style='width:%dpx'>"
                "<div class='markdown-preview-sizer'>%s</div></div>" % (cw, card))
        page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
                + "</style>" + JS + "</head><body>" + body + "</body></html>")
        hp = os.path.join(out, "w.html"); open(hp, "w", encoding="utf-8").write(page)
        r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--virtual-time-budget=2000",
                            "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                            "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
        g = re.search(r'<div id="R">(.*?)</div>', r.stdout or "", re.S)
        row.append(g.group(1) if g else "NO RESULT")
    print("card %d\n   900px pane: %s\n  1600px pane: %s" % (i + 1, row[0], row[1]))
