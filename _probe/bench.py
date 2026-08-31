"""THE READER'S YARDSTICK: the pixels-first reading against 60 rows read by eye.

`_probe/pixfirst-test/truth.json` holds four Finder list panes from the video,
every row and every column typed out from the frames by hand -- including the
truncations the SCREEN makes, because that is what the pixels say and a reader
that "corrects" them is inventing.

Run it after any change to the reader:   python _probe/bench.py [--time]
It prints rows right, cells right, and the seconds taken, and every miss with
the truth beside the reading, so a change that trades one fault for another is
visible instead of hidden inside a total.
"""
import sys, os, json, time, difflib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import pixfirst

TRUTH = os.path.join(HERE, "pixfirst-test", "truth.json")
IMG = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"


def run(show=True):
    truth = json.load(open(TRUTH, encoding="utf-8"))
    rows_ok = rows_all = cells_ok = cells_all = 0
    t0 = time.time()
    misses = []
    shape = []
    for pane in truth["panes"]:
        path = os.path.join(IMG, pane["frame"] + ".png")
        rec = pixfirst.read_frame(path, None, "", wb=pane["wb"], list_box=True)
        all_rows = rec.get("rows") or []
        got = [[(c or "").strip() for c in (r.get("cells") or [])]
               for r in all_rows if not r.get("cut")]
        want = pane["rows"]
        # HOW MANY ROWS, BEFORE HOW WELL THEY READ. A row the reader found
        # and marked cut scores zero on every cell and looks, in a total, like
        # a row it never saw. The two are not the same thing and the last row
        # of two of these panes is exactly that case: clipped by the path bar,
        # found, marked cut, dropped. Printed here so a change that keeps a
        # cut row is visible as what it is.
        shape.append((pane["frame"], len(want), len(got), len(all_rows) - len(got)))
        rows_all += len(want)
        for i, w in enumerate(want):
            g = got[i] if i < len(got) else []
            same = True
            for j, wc in enumerate(w):
                gc = g[j] if j < len(g) else ""
                cells_all += 1
                if gc == wc:
                    cells_ok += 1
                else:
                    same = False
                    misses.append((pane["frame"], i, j, wc, gc))
            if same:
                rows_ok += 1
    took = time.time() - t0
    if show:
        for frame, i, j, wc, gc in misses:
            print("  %s row %-2d col %d  want %-30r got %r" % (frame, i, j, wc, gc))
        for frame, w_, g_, cut_ in shape:
            print("  %s  truth %d rows, read %d, %d more found and marked cut"
                  % (frame, w_, g_, cut_))
        print("ROWS  %d of %d" % (rows_ok, rows_all))
        print("CELLS %d of %d" % (cells_ok, cells_all))
        print("TOOK  %.1f s" % took)
        try:
            print(pixfirst.memory_report())
        except Exception:
            pass
    return rows_ok, rows_all, cells_ok, cells_all, took


if __name__ == "__main__":
    run()
