import sys, os, re, subprocess
sys.path.insert(0, "/mnt/g/AI/Ethereal/ui-extractor"); os.chdir("/mnt/g/AI/Ethereal/ui-extractor")
import compare
note = open("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Move Memory Files Out of Claude Code Into Obsidian.md", encoding="utf-8").read()
cards = [l for l in note.splitlines() if l.startswith('<div class="sn-window sn-obsidian')]
css = open(compare.CSS_PATH, encoding="utf-8").read()
out = "/mnt/g/AI/Ethereal/ui-extractor/_probe/wmeas"; os.makedirs(out, exist_ok=True)
JS = ("<script>window.addEventListener('load',function(){var q=function(s){var e=document.querySelector(s);"
      "return e?e.offsetWidth:-1};document.title='MEAS win='+q('.sn-window')+' ribbon='+q('.sn-ribbon')"
      "+' tree='+q('.sn-explorer')+' blank='+q('.sn-blank')+' doc='+q('.sn-doc');});</script>")
for i, card in enumerate(cards):
    g = re.search(r'grid-template-columns: ([^"]+)"', card)
    for cw in (760, 1200):
        body = ("<div class='markdown-preview-view screen-note' style='width:%dpx'>"
                "<div class='markdown-preview-sizer'>%s</div></div>" % (cw, card))
        page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
                + "</style>" + JS + "</head><body>" + body + "</body></html>")
        hp = os.path.join(out, "q.html"); open(hp, "w", encoding="utf-8").write(page)
        r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--virtual-time-budget=2000",
                            "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                            "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
        m = re.search(r"MEAS win=(-?\d+) ribbon=(-?\d+) tree=(-?\d+) blank=(-?\d+) doc=(-?\d+)", r.stdout or "")
        print("card %d  cols=%-42s  container %4d -> %s" % (i+1, (g.group(1) if g else "?")[:42], cw,
                                                            m.group(0)[5:] if m else "NO MEASUREMENT"))
