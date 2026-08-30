"""diagB: verify the striped-fill proposal on a COPY of the note (diagnosis only).

    python3 _probe/diagB-fill.py <js-file> [--cards|--pics] [--orig] [--shot]

Writes the copy of the note and a test stylesheet under the diagB tmp dir and
nothing else; --orig renders the real note with the real stylesheet instead,
for a before/after diff. --shot also asks Edge for a screenshot of the page,
written into the same tmp dir over \\wsl.localhost."""
import os, re, sys, subprocess
BUILD = "/mnt/g/AI/Ethereal/ui-extractor"
TMP = "/home/trism/.claude/jobs/014c964f/tmp/diagB"
sys.path.insert(0, BUILD); sys.path.insert(0, BUILD + "/_probe"); os.chdir(BUILD)
import compare, dom

def with_fill(line):
    # what furnish.py would write: after </table>, a fill whose class carries
    # the parity of the NEXT row (odd rows are the shaded ones, head counted)
    def sub(m):
        n = m.group(0).count("<tr")
        cls = "sn-fill-odd" if n % 2 == 0 else "sn-fill-even"
        return m.group(0) + '<div class="sn-fill %s"></div>' % cls
    return re.sub(r'<table class="sn-list">.*?</table>', sub, line)

orig = "--orig" in sys.argv
mode = "--pics" if "--pics" in sys.argv else "--cards"
js = open(sys.argv[1], encoding="utf-8").read()
note = BUILD + "/_probe/note-f12.md"
if not orig:
    src = open(note, encoding="utf-8").read().split("\n")
    note = TMP + "/note-f12-diagB.md"
    open(note, "w", encoding="utf-8").write("\n".join(with_fill(l) for l in src))
    css = TMP + "/screen-notes-diagB.css"
    open(css, "w", encoding="utf-8").write(open(compare.CSS_PATH, encoding="utf-8").read()
                                           + open(TMP + "/diagB-extra.css", encoding="utf-8").read())
    compare.CSS_PATH = css
pics, cards = compare.parts_of(note)
frags = [c[2] for c in cards] if mode == "--cards" else [p[2] for p in pics]
print(dom.run(frags, js))
if "--shot" in sys.argv:
    hp = BUILD + "/_probe/dom/p.html"
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    png = r"\\wsl.localhost\%s%s" % (distro, (TMP + "/shot-%s.png" % ("orig" if orig else "diagB")).replace("/", "\\"))
    r = subprocess.run([compare.EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        "--user-data-dir=" + compare.win_path(BUILD + "/_probe/dom/prof"),
                        "--window-size=1000,%d" % int(sys.argv[sys.argv.index("--shot") + 1]),
                        "--screenshot=" + png, compare.file_url(hp)], capture_output=True, text=True, timeout=300)
    print("screenshot ->", png, "| exists:", os.path.exists(TMP + "/shot-%s.png" % ("orig" if orig else "diagB")))
