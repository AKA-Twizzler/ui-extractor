import sys, os, re, subprocess
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir("/home/trism/.claude/jobs/014c964f/tmp/replay")
import compare
note = open("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Move Memory Files Out of Claude Code Into Obsidian.md", encoding="utf-8").read()
card = [l for l in note.splitlines() if l.startswith('<div class="sn-window sn-obsidian')][3]
css_new = open(compare.CSS_PATH, encoding="utf-8").read()
css_old = css_new[:css_new.index("/* A REBUILT WINDOW IS A PICTURE")]
# Obsidian's own readable-line-length, exactly as it applies it
OBS = ".markdown-preview-view.is-readable-line-width .markdown-preview-sizer{max-width:var(--file-line-width,700px);}"
out = "/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/wmeas"
JS = ("<script>window.addEventListener('load',function(){var q=function(s){var e=document.querySelector(s);"
      "return e?e.offsetWidth:-1};document.title='MEAS win='+q('.sn-window')+' tree='+q('.sn-explorer')"
      "+' doc='+q('.sn-doc');});</script>")
for label, css in (("WITHOUT the rule", css_old), ("WITH the rule   ", css_new)):
    body = ("<div class='markdown-preview-view screen-note is-readable-line-width' style='width:1500px'>"
            "<div class='markdown-preview-sizer'>%s</div></div>" % card)
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + OBS + css
            + "</style>" + JS + "</head><body>" + body + "</body></html>")
    hp = os.path.join(out, "r.html"); open(hp, "w", encoding="utf-8").write(page)
    r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--virtual-time-budget=2000",
                        "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                        "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
    m = re.search(r"MEAS win=(-?\d+) tree=(-?\d+) doc=(-?\d+)", r.stdout or "")
    print("%s  in a 1500px pane with readable-line-width ON -> %s" % (label, m.group(0)[5:] if m else "NO MEASUREMENT"))
