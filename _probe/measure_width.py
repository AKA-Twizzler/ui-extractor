import sys, os, re, subprocess, json
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir("/home/trism/.claude/jobs/014c964f/tmp/replay")
import compare
note = open("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Move Memory Files Out of Claude Code Into Obsidian.md", encoding="utf-8").read()
card = next(l for l in note.splitlines() if l.startswith('<div class="sn-window sn-obsidian'))
css_new = open(compare.CSS_PATH, encoding="utf-8").read()
css_old = css_new.replace("calc(1200 * var(--sn-u, 1px))", "calc(880 * var(--sn-u, 1px))")
css_old = css_old[:css_old.index("/* A REBUILT WINDOW IS A PICTURE")]
out = "/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/wmeas"; os.makedirs(out, exist_ok=True)
JS = ("<script>window.addEventListener('load',function(){"
      "var w=document.querySelector('.sn-window');"
      "var s=document.querySelector('.markdown-preview-sizer');"
      "var e=document.querySelector('.sn-explorer')||document.querySelector('.sn-tree');"
      "document.title='MEAS window='+(w?w.offsetWidth:-1)+' sizer='+(s?s.offsetWidth:-1)"
      "+' sidebar='+(e?e.offsetWidth:-1);});</script>")
for label, css in (("BEFORE (880 cap, no container rule)", css_old), ("AFTER  (my change)", css_new)):
    for cw in (700, 1400):
        body = ("<div class='markdown-preview-view screen-note' style='width:%dpx'>"
                "<div class='markdown-preview-sizer'>%s</div></div>" % (cw, card))
        page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
                + "</style>" + JS + "</head><body>" + body + "</body></html>")
        hp = os.path.join(out, "p.html"); open(hp, "w", encoding="utf-8").write(page)
        r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                            "--virtual-time-budget=2000",
                            "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                            "--dump-dom", compare.file_url(hp)],
                           capture_output=True, text=True, timeout=120)
        m = re.search(r"MEAS window=(-?\d+) sizer=(-?\d+) sidebar=(-?\d+)", r.stdout or "")
        print("%-38s container %4d ->  %s" % (label, cw, m.group(0)[5:] if m else "NO MEASUREMENT"))
