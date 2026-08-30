import sys, os, re, subprocess
sys.path.insert(0, "/mnt/g/AI/Ethereal/ui-extractor"); os.chdir("/mnt/g/AI/Ethereal/ui-extractor")
import compare
note = open("_probe/note-ratio2.md", encoding="utf-8").read()
cards = [l for l in note.splitlines() if l.startswith('<div class="sn-window sn-')]
css = open(compare.CSS_PATH, encoding="utf-8").read()
out = "/mnt/g/AI/Ethereal/ui-extractor/_probe/wmeas"; os.makedirs(out, exist_ok=True)
JS = ("<script>window.addEventListener('load',function(){var e=document.querySelector('.sn-window');"
      "document.title='MEAS w='+(e?e.offsetWidth:-1)+' h='+(e?e.offsetHeight:-1);});</script>")
print("%-4s %-34s %-28s %-28s" % ("card", "asked for", "in a 900px pane", "in a 1600px pane"))
for i, card in enumerate(cards[:12]):
    m = re.search(r'--sn-ratio:([\d.]+)(?:;--sn-max:([\d.]+)%)?', card)
    want_r = float(m.group(1)) if m else 0
    want_s = float(m.group(2)) if (m and m.group(2)) else 100.0
    res = []
    for cw in (900, 1600):
        body = ("<div class='markdown-preview-view screen-note' style='width:%dpx'>"
                "<div class='markdown-preview-sizer'>%s</div></div>" % (cw, card))
        page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
                + "</style>" + JS + "</head><body>" + body + "</body></html>")
        hp = os.path.join(out, "s.html"); open(hp, "w", encoding="utf-8").write(page)
        r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--virtual-time-budget=2000",
                            "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                            "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
        g = re.search(r"MEAS w=(-?\d+) h=(-?\d+)", r.stdout or "")
        if g:
            w, h = int(g.group(1)), int(g.group(2))
            res.append("%4dx%-5d ratio %.2f w/pane %2.0f%%" % (w, h, h/max(1,w), 100*w/cw))
        else:
            res.append("NO MEASUREMENT")
    print("%-4d shape %.2f, width %5.1f%%      %-28s %-28s" % (i+1, want_r, want_s, res[0], res[1]))
