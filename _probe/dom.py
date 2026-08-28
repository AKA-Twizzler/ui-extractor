"""Render note fragments the way compare.py does and run a JS probe on them.

    python3 _probe/dom.py <note.md> <js-file-or-inline> [--stages | --cards] [--width 960]

The JS runs after load and must set document.getElementById('R').textContent
(one line per finding). Prints the result per fragment."""
import os, re, subprocess, sys
sys.path.insert(0, "/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir("/home/trism/.claude/jobs/014c964f/tmp/replay")
import compare

def run(fragments, js, width=960, cell_h=None):
    css = open(compare.CSS_PATH, encoding="utf-8").read()
    out = "/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/dom"
    body = "".join("<div class='cell' data-i='%d'><div class='markdown-preview-view screen-note' style='width:%dpx'>"
                   "<div class='markdown-preview-sizer'>%s</div></div></div>" % (i, width, f)
                   for i, f in enumerate(fragments))
    page = ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
            + "</style><script>window.addEventListener('load',function(){var R=document.createElement('pre');R.id='R';"
            "try{" + js + "}catch(e){R.textContent='JS ERROR '+e;}document.body.appendChild(R);});</script>"
            "</head><body>" + body + "</body></html>")
    hp = os.path.join(out, "p.html"); open(hp, "w", encoding="utf-8").write(page)
    r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                        "--virtual-time-budget=3000", "--window-size=1200,900",
                        "--user-data-dir=" + compare.win_path(os.path.join(out, "prof")),
                        "--dump-dom", compare.file_url(hp)], capture_output=True, text=True, timeout=180)
    g = re.search(r'<pre id="R">(.*?)</pre>', r.stdout or "", re.S)
    import html as H
    return H.unescape(g.group(1)) if g else "NO RESULT\n" + (r.stderr or "")[-500:]

if __name__ == "__main__":
    note = sys.argv[1]; js = sys.argv[2]
    if os.path.exists(js): js = open(js, encoding="utf-8").read()
    width = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 960
    pics, cards = compare.parts_of(note)
    frags = [c[2] for c in cards] if "--cards" in sys.argv else [p[2] for p in pics]
    print(run(frags, js, width))
