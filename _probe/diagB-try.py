"""diagB (diagnosis only): render a note's cards with the vault stylesheet PLUS
an extra stylesheet, run a JS probe, and screenshot chosen cards so the stripes
can be measured off real pixels.

    python3 _probe/diagB-try.py <note.md> <extra.css|-> <js-file> <outdir> [card-index ...]

Nothing here writes to the build folder except this file's own outputs in <outdir>.
"""
import os, re, subprocess, sys
sys.path.insert(0, "/mnt/g/AI/Ethereal/ui-extractor"); os.chdir("/mnt/g/AI/Ethereal/ui-extractor")
import compare

DISTRO = os.environ.get("WSL_DISTRO_NAME", "Ubuntu-24.04")

def wpath(p):
    """Windows-side path for a WSL path, /mnt/<letter> or the UNC share."""
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    if m:
        return m.group(1).upper() + ":\\" + m.group(2).replace("/", "\\")
    return "\\\\wsl.localhost\\" + DISTRO + p.replace("/", "\\")

def furl(p):
    return "file:///" + wpath(p).replace("\\", "/").replace(" ", "%20")

PROF = "/mnt/g/AI/Ethereal/ui-extractor/_probe/dom/prof"

note, extra, jsf, outdir = sys.argv[1:5]
idx = [int(x) for x in sys.argv[5:] if x.isdigit()]
os.makedirs(outdir, exist_ok=True)
css = open(compare.CSS_PATH, encoding="utf-8").read()
if extra != "-":
    css += "\n" + open(extra, encoding="utf-8").read()
js = open(jsf, encoding="utf-8").read()
pics, cards = compare.parts_of(note)
frags = [p_[2] for p_ in pics] if "--pics" in sys.argv else [c[2] for c in cards]

def page_of(fs, width=960, cell_h=None):
    body = "".join("<div class='cell' data-i='%d'%s><div class='markdown-preview-view screen-note' "
                   "style='width:%dpx'><div class='markdown-preview-sizer'>%s</div></div></div>"
                   % (i, (" style='height:%dpx'" % cell_h) if cell_h else "", width, f)
                   for i, f in enumerate(fs))
    return ("<!doctype html><html><head><meta charset='utf-8'><style>" + compare.VARS + css
            + "</style><script>window.addEventListener('load',function(){var R=document.createElement('pre');R.id='R';"
              "try{" + js + "}catch(e){R.textContent='JS ERROR '+e;}document.body.appendChild(R);});</script>"
              "</head><body>" + body + "</body></html>")

# 1. the DOM measurement over every card
hp = os.path.join(outdir, "measure.html")
open(hp, "w", encoding="utf-8").write(page_of(frags))
r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--virtual-time-budget=3000", "--window-size=1200,900",
                    "--user-data-dir=" + wpath(PROF),
                    "--dump-dom", furl(hp)], capture_output=True, text=True, timeout=300)
g = re.search(r'<pre id="R">(.*?)</pre>', r.stdout or "", re.S)
import html as H
print(H.unescape(g.group(1)) if g else "NO RESULT\n" + (r.stderr or "")[-800:])

# 2. one screenshot per asked-for card, at compare.py's own cell height
for i in idx:
    name = "card-%02d" % (i + 1)
    hp2 = os.path.join(outdir, name + ".html")
    open(hp2, "w", encoding="utf-8").write(page_of([frags[i]], cell_h=compare.CARD_CELL))
    png = os.path.join(outdir, name + ".png")
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                    "--user-data-dir=" + wpath(PROF),
                    "--window-size=1000,%d" % compare.CARD_CELL,
                    "--screenshot=" + wpath(png), furl(hp2)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    print("shot", png, "exists", os.path.exists(png))
