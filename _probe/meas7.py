import sys, os, re, subprocess
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir("/home/trism/.claude/jobs/014c964f/tmp/replay")
import compare
note = open("_probe/note-ratio.md", encoding="utf-8").read()
cards = [l for l in note.splitlines() if l.startswith('<div class="sn-window sn-')]
css = open(compare.CSS_PATH, encoding="utf-8").read()
out = "/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/wmeas"
JS = ("<script>window.addEventListener('load',function(){var e=document.querySelector('.sn-window');"
      "var c=getComputedStyle(e);var d=document.createElement('div');d.id='R';"
      "d.textContent='inline['+e.getAttribute('style')+'] maxw['+c.maxWidth+'] parent['"
      "+e.parentElement.offsetWidth+'] w['+e.offsetWidth+'] h['+e.offsetHeight+']';"
      "document.body.appendChild(d);});</script>")
print("cards found on their own lines: %d" % len(cards))
for i, card in enumerate(cards[:3]):
    body = ("<div class='markdown-preview-view screen-note' style='width:900px'>"
            "<div class='markdown-preview-sizer'>%s</div></div>" % card)
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
            + "</style>" + JS + "</head><body>" + body + "</body></html>")
    hp = os.path.join(out, "u.html"); open(hp, "w", encoding="utf-8").write(page)
    r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--virtual-time-budget=2000",
                        "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                        "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
    g = re.search(r'<div id="R">(.*?)</div>', r.stdout or "", re.S)
    print("card %d: %s" % (i + 1, g.group(1) if g else "NO RESULT"))
