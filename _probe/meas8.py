import sys, os, re, subprocess
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir("/home/trism/.claude/jobs/014c964f/tmp/replay")
import compare
css = open(compare.CSS_PATH, encoding="utf-8").read()
out = "/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/wmeas"
JS = ("<script>window.addEventListener('load',function(){var o='';"
      "document.querySelectorAll('.sn-window').forEach(function(e,i){var c=getComputedStyle(e);"
      "o+=i+': maxw='+c.maxWidth+' w='+e.offsetWidth+' | ';});"
      "var d=document.createElement('div');d.id='R';d.textContent=o;document.body.appendChild(d);});</script>")
cases = [
  ('ratio then max-width', '<div class="sn-window sn-finder sn-dark" style="--sn-ratio:0.70;max-width:48.6%"><div class="sn-body">x</div></div>'),
  ('max-width then ratio', '<div class="sn-window sn-finder sn-dark" style="max-width:48.6%;--sn-ratio:0.70"><div class="sn-body">x</div></div>'),
  ('max-width alone     ', '<div class="sn-window sn-finder sn-dark" style="max-width:48.6%"><div class="sn-body">x</div></div>'),
  ('width alone         ', '<div class="sn-window sn-finder sn-dark" style="width:48.6%"><div class="sn-body">x</div></div>'),
]
body = "<div class='markdown-preview-view screen-note' style='width:900px'><div class='markdown-preview-sizer'>" \
       + "".join(h for _, h in cases) + "</div></div>"
page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
        + "</style>" + JS + "</head><body>" + body + "</body></html>")
hp = os.path.join(out, "v.html"); open(hp, "w", encoding="utf-8").write(page)
r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--virtual-time-budget=2000",
                    "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                    "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=120)
g = re.search(r'<div id="R">(.*?)</div>', r.stdout or "", re.S)
res = (g.group(1) if g else "NO RESULT").split(" | ")
for (label, _), v in zip(cases, res):
    print("  %s -> %s" % (label, v))
