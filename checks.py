#!/usr/bin/env python3
"""Every stage, checked against a frame whose answer is known.

    python3 checks.py              every stage
    python3 checks.py tree chat    only stages whose name contains these
    python3 checks.py --list       what there is to run

Why this exists, in the words of the fault that caused it: a wrong answer got
into the output that neither scored fixture covered. The fallback that prints
loose text off a pane nothing else could place stated "R78" from Jared's
visualizer as fact. One engine reads R78 there, the other reads Ris, and the
marks are three faint shapes on near-black that Tristan cannot see at all.
Nothing was lying; nothing was checking either.

Both fixtures passed that whole time, because the fault was not in what they
measure. So every stage now has at least one frame whose answer is known --
including the stages whose whole job is to REFUSE, which is where the wrong
answers come from and which no score had ever covered.

The frames are not kept in the repository. They are cut from the library on
demand by the same capture the pipeline uses, and land where the vault's rule
says captured images live: G:\\Images\\<Video Title>\\HH-MM-SS.png. So there
are no binary fixtures to drift, and running this twice costs the capture once.

A check states what it expects in plain terms and fails loudly. A check that
cannot run -- a video missing from the library -- says SKIP and does not
pretend to have passed.
"""
import glob
import os
import sys
import traceback

import cv2

import capture
import chat_reader
import columns
import console_reader
import machine
import note_reader
import overlay
import panes
import screenness
import tree_reader
import verify_names

VIDEOS = {
    "obsidian": "How To Set Up Claude Code With Obsidian",
    "install": "Install Claude Code and-or the AI Memory Vault",
    "works": "How Claude Code Actually Works",
    "jarvis": "My AI Jarvis Makes Money. Here's How",
    "july6": "Live Replay - July 6, 2026; AI marketing, Jarvis builds, and AI automation",
    "stjude": "Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26",
    "aug03": "Live August 03",
}

_ENGINE = None
_FRAMES = {}
_REGIONS = {}


def engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE


class Skip(Exception):
    """This check cannot run here, and says so rather than passing."""


def video(key):
    folder = machine.here(f"/mnt/g/Video/{VIDEOS[key]}")
    found = sorted(glob.glob(os.path.join(folder, "*.mp4")))
    if not found:
        raise Skip(f"no video in the library for {key!r}")
    return found[0]


def frame(key, stamp):
    """The frame at this moment, captured once and kept where images live."""
    if (key, stamp) in _FRAMES:
        return _FRAMES[(key, stamp)]
    out_dir = machine.here(f"/mnt/g/Images/{VIDEOS[key]}")
    path = os.path.join(out_dir, stamp.replace(":", "-") + ".png")
    if not os.path.exists(path):
        path, _ = capture.capture_moment(video(key), stamp, out_dir)
    _FRAMES[(key, stamp)] = path
    return path


def regions(key, stamp):
    """Every region of that frame, cut out and written, left to right."""
    if (key, stamp) in _REGIONS:
        return _REGIONS[(key, stamp)]
    path = frame(key, stamp)
    img = cv2.imread(path)
    out = []
    for i, box in enumerate(panes.frame_regions(img, engine=engine())):
        cut = path.replace(".png", f"_r{i}.png")
        if panes.write_box(img, box, cut) is not None:
            out.append(cut)
    _REGIONS[(key, stamp)] = out
    return out


CHECKS = []


def check(name):
    def take(fn):
        CHECKS.append((name, fn))
        return fn
    return take


# ------------------------------------------------------------ the machine

@check("machine: paths and programs")
def _machine():
    if machine.TESSERACT is None:
        return False, "no tesseract; two engines are the method here"
    import shutil
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return False, "ffmpeg or ffprobe is not on the path"
    for p in ("/mnt/g/Images", "/mnt/g/Video", "/mnt/nas/obsidian-vault"):
        if not os.path.isdir(machine.here(p)):
            return False, f"{p} does not resolve to anything on this machine"
    return True, f"tesseract at {machine.TESSERACT}, drives resolve"


# ------------------------------------------------------------ the capture

@check("capture: a moment becomes a picture")
def _capture():
    path = frame("obsidian", "00:02:09")
    img = cv2.imread(path)
    if img is None:
        return False, "captured nothing"
    if img.shape[1] < 640:
        return False, f"came back {img.shape[1]}px wide; that is not a frame"
    return True, f"{os.path.basename(path)} at {img.shape[1]}x{img.shape[0]}"


# ------------------------------------------------- screen against camera

@check("screenness: interface against camera")
def _screenness():
    desk = cv2.imread(frame("jarvis", "00:02:00"))
    room = cv2.imread(frame("stjude", "02:12:59"))
    a = sum(x["share"] for x in screenness.ui_regions(desk, engine())) * 100
    b = sum(x["share"] for x in screenness.ui_regions(room, engine())) * 100
    if not a > 50:
        return False, f"a desktop measured {a:.0f}% interface; it is a screen"
    if not b < 50:
        return False, f"a live stream measured {b:.0f}% interface; it is a room"
    return True, f"desktop {a:.0f}%, live stream {b:.0f}%"


# ------------------------------------------------------------ the windows

@check("windows: a desktop has them, one window does not")
def _windows():
    desk = overlay.windows(cv2.imread(frame("jarvis", "00:02:00")))
    if len(desk) < 2:
        return False, f"found {len(desk)} windows on a desktop carrying three"
    for key, stamp, what in (("obsidian", "00:02:09", "an Obsidian window"),
                             ("install", "00:02:42", "a terminal")):
        got = overlay.windows(cv2.imread(frame(key, stamp)))
        if got:
            return False, f"found {len(got)} windows on {what}, which is one window"
    return True, f"{len(desk)} on the desktop, none on either single window"


@check("regions: a desktop splits, a window keeps its panes")
def _regions():
    desk = regions("jarvis", "00:02:00")
    if len(desk) < 4:
        return False, f"a desktop split into {len(desk)} regions"
    win = regions("obsidian", "00:02:09")
    if not 2 <= len(win) <= 6:
        return False, f"an Obsidian window split into {len(win)} panes"
    return True, f"desktop {len(desk)} regions, Obsidian {len(win)} panes"


# -------------------------------------------------------------- the tree

@check("tree: the fixture")
def _tree_fixture():
    import fixture
    import score
    pane = regions("obsidian", "00:02:09")[0]
    got = verify_names.verify(pane, tree_reader.read_tree(pane))
    if not got.get("is_tree"):
        return False, f"refused the sidebar: {got.get('layout_verdict')}"
    rows = score.align(score.load_rows_from(got), fixture.load()) \
        if hasattr(score, "align") else None
    counts = score.tally(got["rows"]) if hasattr(score, "tally") else None
    if counts is None:
        # score.py is a program, not a library; run its own comparison
        import json
        tmp = pane.replace(".png", "_tree.json")
        json.dump(got, open(tmp, "w"), indent=2)
        import subprocess
        r = subprocess.run([sys.executable, "score.py", tmp],
                           capture_output=True, text=True, encoding="utf-8")
        text = r.stdout
        need = {"folder vs file": 31, "depth": 31, "open vs closed": 31}
        for line in text.splitlines():
            for label, want in need.items():
                if line.strip().startswith(label):
                    n = int(line.split()[-1].split("/")[0])
                    if n < want:
                        return False, f"{label} {n}/31: {line.strip()}"
        names = [l for l in text.splitlines() if "names, exact" in l]
        if not names:
            return False, "the scorer said nothing about names"
        n = int(names[0].split()[-1].split("/")[0])
        if n < 30:
            return False, f"names {n}/31"
        return True, f"names {n}/31, structure 31/31 on all three"
    return True, "scored"


@check("tree: refuses what is not a tree")
def _tree_refuses():
    bad = []
    for pane in regions("jarvis", "00:02:00"):
        got = tree_reader.read_tree(pane)
        if got.get("is_tree") and len(got.get("rows") or []) >= 5:
            bad.append(os.path.basename(pane))
    if bad:
        return False, ("read a file tree off a desktop that has none: "
                       + ", ".join(bad))
    return True, "no file tree claimed on a desktop that has none"


@check("tree: a faint chevron is still a folder")
def _tree_chevron():
    pane = regions("obsidian", "00:06:00")[0]
    got = tree_reader.read_tree(pane)
    if not got.get("is_tree"):
        return False, f"refused the sidebar: {got.get('layout_verdict')}"
    found = [r for r in got["rows"] if "course" in r["name"].lower()]
    if not found:
        return False, "did not read the Courses row at all"
    row = found[0]
    if row["kind"] != "folder" or row["chevron"] != "right":
        return False, (f"Courses came back {row['kind']} / {row['chevron']}; "
                       "it is a collapsed folder")
    return True, "Courses reads as a collapsed folder"


# ---------------------------------------------------------- the terminal

@check("terminal: the fixture")
def _console_fixture():
    import subprocess
    path = frame("install", "00:02:42")
    r = subprocess.run([sys.executable, "score_console.py", path],
                       capture_output=True, text=True, encoding="utf-8")
    # the SUMMARY line, not the per-line counts, which also say "characters"
    line = [l for l in r.stdout.splitlines()
            if l.strip().startswith("characters")]
    if not line:
        return False, f"the scorer said nothing: {r.stdout[-200:]}"
    text = line[0]
    chars = int(text.split("characters")[1].split("/")[0])
    typed = text.split("typed-vs-output")[1].split()[0]
    cuts = text.split("cut marks")[1].split()[0]
    if chars < 330:
        return False, f"characters {chars}/360"
    if typed != "9/9" or cuts != "9/9":
        return False, f"typed {typed}, cut marks {cuts}"
    return True, f"characters {chars}/360, typed {typed}, cut marks {cuts}"


@check("terminal: refuses what is not a terminal")
def _console_refuses():
    for pane in regions("obsidian", "00:02:09"):
        got = console_reader.read_console(pane)
        if got.get("is_console"):
            return False, f"read {os.path.basename(pane)} as a terminal"
    for pane in regions("jarvis", "00:02:00"):
        got = console_reader.read_console(pane)
        if got.get("is_console"):
            return False, (f"read {os.path.basename(pane)} as a terminal; "
                           "the page there is merely set in monospace")
    return True, "no terminal claimed on an Obsidian window or a desktop"


# ------------------------------------------------------------- the table

@check("columns: a Finder window is one table")
def _columns():
    best = None
    for pane in regions("works", "00:07:00"):
        got = columns.read_list(pane)
        if not got.get("is_list"):
            continue
        for block in got["blocks"]:
            rows = len(block.get("rows") or [])
            if best is None or rows > best[0]:
                best = (rows, block)
    if best is None:
        return False, "found no table in a frame showing a Finder window"
    rows, block = best
    heads = [h for h in (block.get("header") or []) if h.strip()]
    # the truth of that window, which is what this has to reproduce: sixteen
    # files under Name / Date Modified / Size / Kind
    want = ("name", "date", "size", "kind")
    said = " ".join(heads).lower()
    missing = [w for w in want if w not in said]
    if missing:
        return False, (f"the table is headed {heads}; that is a row of the "
                       f"window's own data, not its headings (no {missing})")
    if rows < 14:
        return False, f"{rows} rows under the right headings; the window holds 16"
    return True, f"{rows} rows under {len(heads)} headings: {' / '.join(heads)}"


@check("regions: the desktop's Clock reads as its lap table")
def _desktop_clock():
    """Tristan's fifth item, pinned. The screen that had no reader turned out
    to be a whole desktop, and the Clock app on it is the one thing there with
    a real table in it: a lap number against two times."""
    for pane in regions("jarvis", "00:01:30"):
        got = columns.read_list(pane)
        if not got.get("is_list"):
            continue
        for block in got["blocks"]:
            said = " ".join(block.get("header") or []).lower()
            body = " ".join(" ".join(r) for r in (block.get("rows") or [])).lower()
            if "lap" in said or "lap" in body:
                return True, (f"{len(block['rows'])} rows under "
                              f"{block.get('header')}")
    return False, "the Clock app's lap table was not read off the desktop"


# -------------------------------------------------------------- the chat

@check("chat: a real log reads, and proves its words")
def _chat_reads():
    got = [chat_reader.read_chat(p, engine=engine())
           for p in regions("july6", "00:40:36")]
    logs = [g for g in got if g.get("is_chat")]
    if not logs:
        why = "; ".join(str(g.get("why"))[:60] for g in got)
        return False, f"no chat log found in a frame showing one: {why}"
    entries = max(len(g["entries"]) for g in logs)
    if entries < 3:
        return False, f"the log came back with {entries} entries"
    return True, f"{len(logs)} log with {entries} entries"


@check("chat: refuses a picture of text")
def _chat_refuses():
    for pane in regions("jarvis", "00:02:00"):
        got = chat_reader.read_chat(pane, engine=engine())
        if got.get("is_chat"):
            return False, (f"read {os.path.basename(pane)} as a chat log; "
                           "the visualizer is not people talking")
    return True, "no chat log claimed on a desktop that has none"


# --------------------------------------------------------- the document

@check("document: counts the lines it read, not the ones it wrote")
def _note_gate():
    real = note_reader.read_note(regions("obsidian", "00:02:09")[2])
    if note_reader.body_lines(real["markdown"]) < 3:
        return False, "a real note did not come back as a document"
    for pane in regions("jarvis", "00:02:00")[:1]:
        got = note_reader.read_note(pane)
        if note_reader.body_lines(got["markdown"]) >= 3:
            return False, (f"{os.path.basename(pane)} came back as a document; "
                           "the visualizer is not one")
    return True, "a note is a document, the visualizer is not"


# ------------------------------------------------------------ the overlay

@check("overlay: a panel drawn on a live stream")
def _panels():
    path = frame("stjude", "02:12:59")
    got = overlay.read_overlays(path, engine())["panels"]
    if not got:
        return False, "found no panel on a frame carrying a donation card"
    said = " ".join(" ".join(p["lines"]) for p in got).lower()
    if "donation" not in said:
        return False, f"found {len(got)} panels but no donation card: {said[:80]}"
    return True, f"{len(got)} panels, the donation card among them"


@check("overlay: the banner, and nothing else")
def _standing():
    path = frame("stjude", "02:12:59")
    looks = overlay.frames_across(video("stjude"), 7979,
                                  workdir=os.path.dirname(path) + "/_looks")
    got = [g["text"] for g in overlay.standing_text(looks, engine=engine())]
    if not any("jaredrhod" in t.lower() for t in got):
        return False, f"did not admit the banner; admitted {got}"
    stray = [t for t in got if "jaredrhod" not in t.lower()]
    if stray:
        return False, f"admitted the room as well: {stray}"
    return True, f"admitted {got}"


# --------------------------------------------------- nothing unconfirmed

@check("confirmation: says which readings are backed")
def _confirm():
    pane = regions("jarvis", "00:02:00")[0]
    res, _ = engine()(pane)
    texts = [t for _, t, _ in (res or [])]
    if not texts:
        return False, "read nothing on the visualizer panel"
    marked = verify_names.confirm_readings(pane, texts)
    doubtful = [t for t, ok in marked if not ok]
    if not doubtful:
        return False, ("every reading on the visualizer came back confirmed; "
                       "the other engine cannot read that panel at all")
    if not any(t.strip().upper().startswith("R7") for t in doubtful):
        return False, f"R78 was not among the doubtful: {doubtful}"
    return True, f"{len(doubtful)} of {len(marked)} unconfirmed, R78 among them"


# ----------------------------------------------------------- the words

@check("transcript: the words that go with a screen")
def _transcript():
    import spot
    import transcript
    path = transcript.find(transcript.title_of(video("jarvis")))
    if path is None:
        return False, "found no transcript for a video that has one"
    cues = transcript.load(path)
    if len(cues) < 20:
        return False, f"the transcript loaded {len(cues)} lines"
    return True, f"{len(cues)} lines of transcript found and read"


def main():
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--list" in sys.argv:
        for name, _ in CHECKS:
            print(" ", name)
        return 0
    runs = [(n, f) for n, f in CHECKS
            if not wanted or any(w.lower() in n.lower() for w in wanted)]
    bad = 0
    for name, fn in runs:
        try:
            ok, detail = fn()
        except Skip as exc:
            print(f"  SKIP  {name}\n          {exc}")
            continue
        except Exception:
            print(f"  BROKE {name}")
            print("          " + traceback.format_exc().strip().splitlines()[-1])
            bad += 1
            continue
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}\n          {detail}")
        if not ok:
            bad += 1
    print(f"\n{len(runs) - bad} of {len(runs)} stages hold"
          + ("" if not bad else f"; {bad} do not"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
