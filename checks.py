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
import re
import subprocess
import sys
import traceback

import cv2
import numpy as np

import capture
import chat_reader
import columns
import console_reader
import machine
import note_reader
import overlay
import panes
import pipeline
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
    # a designed slide rather than a screen recording: monospace throughout,
    # cards in drawn rectangles, dim text. Every gate in the build meets
    # something here it was never shown while it was being built.
    "skills": "How To Make Your Own AI Skills",
    # a second Finder window, in a different video, on a desktop beside an
    # Obsidian window -- so the table's headings are not proved on one frame
    "memfiles": "Move Memory Files Out of Claude Code Into Obsidian",
    # a locked-off camera on a talking head: nothing in the shot moves much,
    # so "stiller than the picture" is at its weakest here
    "beginners": "Claude Code For Beginners; Start Here",
    # a live stream carrying a CAPTION BLOCK -- six lines of wrapped prose,
    # drawn over the room. It is the one shape that is genuinely an overlay
    # AND passes every geometric test a tree has to pass.
    "july31": "Jarvis Raises Money for St. Judes with Epic Performance "
              "- Live Replay July 31, 2026",
    # a second locked-off room, a second camera: printing on a monitor bezel
    # and on a cap, both of which moved exactly as much as what they are
    # printed on
    "leads": "How To Generate Leads With AI",
    # a web page rather than an application: a post with real paragraphs on it
    # and scraps of the site's own chrome scattered through the same column
    "post": "A Look Inside My Million Dollar AI Business",
    # a Finder sidebar, cut so only the right edge of each icon survives: the
    # names are all flush and the ICONS differ in width, which is the one
    # shape that made this build invent nesting that was never on the screen
    "makejarvis": "How To Make A Jarvis",
    # a live stream: banner over camera, a chat column, camera strips between
    # -- the frame the camera-pane gate and the read-again mark are pinned on
    "qna": "Live Q&A Answering Questions About AI Automation",
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
    """The frame at this moment, captured once and kept where images live.

    New captures land in the video's Images/ folder; a frame captured
    before that layout existed is still honoured where it stands.
    """
    if (key, stamp) in _FRAMES:
        return _FRAMES[(key, stamp)]
    out_dir = machine.here(f"/mnt/g/Images/{VIDEOS[key]}")
    name = stamp.replace(":", "-") + ".png"
    path = os.path.join(out_dir, "Images", name)
    old = os.path.join(out_dir, name)
    if not os.path.exists(path):
        if os.path.exists(old):
            path = old
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            path, _ = capture.capture_moment(
                video(key), stamp, os.path.join(out_dir, "Images"))
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


_NOTES = {}


def note_on(key, stamp, needle):
    """The reading of whichever pane of that frame carries this text.

    Anchored on what is written rather than on a pane number: the number moves
    the moment the splitter changes, and a check that breaks when nothing is
    wrong is worse than no check.
    """
    for pane in regions(key, stamp):
        md = _NOTES.get(pane)
        if md is None:
            md = note_reader.read_note(pane)["markdown"]
            _NOTES[pane] = md
        if needle in md:
            return md
    raise Skip(f"no pane of {key} at {stamp} carries {needle!r}")


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


@check("screenness: a window on a photograph is still a window")
def _screenness_wallpaper():
    """The frame that was thrown away whole.

    A desktop with a nebula for a wallpaper: the photograph scores like a
    camera, and the only part of the frame that ties is the Finder window
    itself, which lands in a single cell of the grid. Two cells were required,
    so the frame came back "no readable interface at full size" and a window
    listing CLAUDE.md with its date, size and kind was never read at all.
    """
    img = cv2.imread(frame("works", "00:01:52"))
    got = screenness.ui_regions(img, engine())
    if not got:
        return False, ("a desktop carrying a Finder window reads as no "
                       "interface at all")
    room = screenness.ui_regions(
        cv2.imread(frame("beginners", "00:05:28")), engine())
    if room:
        return False, f"a talking head came back with {len(room)} regions"
    return True, (f"{len(got)} region on the wallpapered desktop, "
                  "none on a talking head")


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


@check("tree: a flat list is not a tree, whatever its icons do")
def _tree_flat_list():
    """Five side-by-side folders whose names are all flush.

    A Finder sidebar's icons differ in width where its names do not, so the
    clipped icons formed one phantom guide column and the pane came back as
    Pictures containing Movies and Desktop: confident, invented, and scoring a
    near-perfect 0.03 row heights of indent miss while it did. Least squares
    fits a flat list perfectly by choosing no slope at all, so the reader now
    also asks that the names MOVE.

    Either answer is truthful here — refusing the pane, or reading it flat —
    so both pass. Only nesting fails.
    """
    WANT = {"applications", "pictures", "movies", "desktop", "documents"}
    sidebar = None
    for pane in regions("makejarvis", "00:00:49"):
        words = {r["text"].strip().lower() for r in tree_reader.ocr_rows(pane)}
        if len(WANT & words) >= 3:
            sidebar = pane
            break
    if sidebar is None:
        raise Skip("no region of How To Make A Jarvis at 00:00:49 "
                   "carries the Finder sidebar")
    got = tree_reader.read_tree(sidebar)
    if not got.get("is_tree"):
        return True, f"refused it: {got.get('layout_verdict')}"
    depths = {r["depth"] for r in got["rows"]}
    if len(depths) > 1:
        drawn = " / ".join("  " * r["depth"] + r["name"] for r in got["rows"])
        return False, f"read nesting off a flat Finder sidebar: {drawn}"
    return True, f"read its {len(got['rows'])} rows flat, nothing invented"


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


@check("overlay: a panel over interface is not an overlay")
def _panel_over_interface():
    """A panel is a rectangle floating over VIDEO.

    On a desktop the same finder catches the application's own cards, and the
    frame came back with seven "panels drawn on the picture" beside the panes
    that had already read them properly -- an Obsidian sidebar among them,
    reading "eee 6aQ Nn ©) Brand Guide". What must NOT change is the stream:
    the donation card floats over a shot of the room and stays.
    """
    keep = []
    for key, stamp, what in (("stjude", "02:12:59", "the donation card"),
                             ("aug03", "00:09:00", "the ended-stream cards")):
        img = cv2.imread(frame(key, stamp))
        pans = overlay.read_overlays(frame(key, stamp), engine())["panels"]
        left = overlay.floating(pans, screenness.ui_regions(img, engine()),
                                img.shape[1], screenness.WORK_WIDTH,
                                overlay.windows(img))
        if len(left) != len(pans) or not left:
            return False, (f"{what}: {len(left)} of {len(pans)} panels kept; "
                           "they float over a room")
        keep.append(f"{what} {len(left)}")
    img = cv2.imread(frame("jarvis", "00:02:00"))
    pans = overlay.read_overlays(frame("jarvis", "00:02:00"), engine())["panels"]
    left = overlay.floating(pans, screenness.ui_regions(img, engine()),
                            img.shape[1], screenness.WORK_WIDTH,
                            overlay.windows(img))
    if left:
        return False, (f"{len(left)} of {len(pans)} panels on a desktop that "
                       f"is all interface: {[p['lines'][0][:30] for p in left]}")
    return True, f"{', '.join(keep)} kept, {len(pans)} on the desktop dropped"


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

    # A locked-off camera is the hard case, and the median let it through. On
    # a talking head -- Jared in his chair, camera fixed -- two stickers on the
    # shelf behind him sat EXACTLY on the frame's median change, 55 against 55
    # and 52 against 55, and were reported as text drawn on the picture.
    #
    # And "stiller than the ground" was not enough either. Printing moves with
    # the thing it is printed on, so a sticker's glyphs change as much as the
    # shelf and no more -- 0.97 of it -- which the comparison admitted. A
    # second room, a second camera: WQHD on a monitor bezel and Hat on Jared's
    # cap, both at 0.97, against 0.32 to 0.65 for everything really drawn.
    for key, moments in (("beginners", (328, 438)), ("leads", (181, 363))):
        for secs in moments:
            looks = overlay.frames_across(
                video(key), secs,
                workdir=machine.here(f"/mnt/g/Images/{VIDEOS[key]}/Images/_looks"))
            room = [g["text"]
                    for g in overlay.standing_text(looks, engine=engine())]
            if room:
                return False, (f"admitted the room off a fixed camera, "
                               f"{key} at {secs}s: {room}")
    return True, f"admitted {got}; nothing off either locked-off camera"


# --------------------------------------------------- nothing unconfirmed

@check("confirmation: says which readings are backed")
def _confirm():
    """The fault this whole suite was built for, pinned to its own frame.

    The pane is found by what is written on it, not by its position in the
    list. It was `regions(...)[0]` until covering the frame properly put the
    menu bar there instead, and a check that moves when the regions move
    reports a fault that is not one.
    """
    seen = []
    for pane in regions("jarvis", "00:02:00"):
        res, _ = engine()(pane)
        texts = [t for _, t, _ in (res or [])]
        marks = [t for t in texts if re.fullmatch(r"[Rr][\dis]\d?", t.strip())]
        if not marks:
            seen.append(f"{os.path.basename(pane)}:{len(texts)}")
            continue
        marked = verify_names.confirm_readings(pane, texts)
        doubtful = [t for t, ok in marked if not ok]
        if not any(t in doubtful for t in marks):
            return False, (f"{marks} came back confirmed, though the other "
                           "engine cannot read that panel at all")
        return True, (f"{len(doubtful)} of {len(marked)} unconfirmed on "
                      f"{os.path.basename(pane)}, {marks} among them")
    return False, ("no pane of the visualizer holds the faint marks any more; "
                   "panes were " + ", ".join(seen))


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


# ------------------------------------------- what a designed slide breaks

@check("note: a card is not a properties panel")
def _props_are_a_column():
    """A wide gap does not make a field; a shared column does.

    The left-hand card of this slide reads "TYPING IT YOURSELF" in letterspaced
    capitals, which splits at a gap wider than three body heights exactly as a
    field does. Taken for a properties block it cost the whole card: everything
    above the last field is dropped as the note's header, so the filename and
    all three bullets went with it and four garbled lines came back in fences.
    """
    card = regions("skills", "00:01:00")[0]
    got = note_reader.read_note(card)
    if got.get("properties"):
        return False, (f"read {len(got['properties'])} properties off a card: "
                       + "; ".join(f"{k}: {v}" for k, v in got["properties"]))
    md = got["markdown"].lower()
    missing = [w for w in ("my-chili-recipe", "brown the meat",
                           "cook a few hours", "season to taste")
               if w not in md]
    if missing:
        return False, "the card came back without " + ", ".join(missing)
    real = note_reader.read_note(regions("obsidian", "00:07:30")[2])
    keys = [k.lower() for k, _ in (real.get("properties") or [])]
    if not all(k in keys for k in ("status", "project", "type", "created")):
        return False, f"a real properties panel came back as {keys}"
    return True, f"the card keeps its bullets; a real panel keeps {keys}"


@check("terminal: refuses a slide set in a terminal font")
def _console_refuses_slides():
    """Jared's slides are drawn as terminals, and they are not terminals.

    Traffic lights, a prompt line, a monospace face throughout -- every test
    this reader had, passed. What gave them away is that a slide has a
    HEADING: one line set larger than the rest, where a terminal has one size
    for everything. Measured off the common advance: two real terminals 0.036
    and 0.052, these three 0.35, 0.35 and 1.28.

    It matters because the lattice fitted to the body then reads the heading
    as noise and drags the body with it -- "rends and nriter real riles" for
    "reads and writes real files" -- and printed it as a terminal transcript.
    """
    slides = [("skills", "00:01:30"), ("skills", "00:03:10")]
    for key, stamp in slides:
        for pane in regions(key, stamp):
            got = console_reader.read_console(pane)
            if got.get("is_console"):
                return False, (f"{stamp} {os.path.basename(pane)} still reads "
                               f"as a terminal: {len(got['lines'])} lines")
    return True, "neither slide is claimed as a terminal"


@check("terminal: says when the other engine disagrees")
def _console_unsettled():
    """The lattice's reading is not evidence on its own.

    The lattice beats the line engine on a real terminal -- 94.2% against
    92.2% -- and that is why its text is the one kept. But it is still one
    engine, and where the two read different LETTERS the line said so nowhere.
    On the fixture the mark lands on the top line, drawn half in colour, and
    on the prompt whose colon the lattice loses.
    """
    real = console_reader.read_console(frame("install", "00:02:42"))
    if not real.get("is_console"):
        return False, f"the terminal fixture was refused: {real.get('why')}"
    marked = [l for l in real["lines"] if l.get("unsettled")]
    if not marked:
        return False, ("not one line marked, though the two engines differ on "
                       "the top line and on the prompt's colon")
    if len(marked) > len(real["lines"]) / 2:
        return False, (f"{len(marked)} of {len(real['lines'])} lines marked; "
                       "a mark on everything means nothing")
    return True, (f"{len(marked)} of {len(real['lines'])} lines marked, "
                  f"first: {marked[0]['second'][:38]!r}")


@check("document: refuses what one engine alone read")
def _note_backed():
    """A document's lines are read twice; nothing had ever looked at the verdict.

    So a live stream's leaderboard came back as prose -- "# 3 & Dr. Paris
    Woods", "a @& Alex Palencia" -- and a frame of its own overlay came back as
    "## +M O L 8 | 0". Measured share of lines the second engine backed: a real
    note 1.00 and 0.89, those two 0.12 and 0.00.
    """
    real = note_reader.read_note(regions("obsidian", "00:07:30")[2])
    if real["backed"] < note_reader.BACKED:
        return False, (f"a real note came back {real['backed']:.2f} backed, "
                       f"under the {note_reader.BACKED:.2f} a document needs")
    worst = None
    for pane in regions("july6", "00:20:00"):
        got = note_reader.read_note(pane)
        if note_reader.body_lines(got["markdown"]) < 3:
            continue
        if got["backed"] >= note_reader.BACKED:
            return False, (f"{os.path.basename(pane)} passed at "
                           f"{got['backed']:.2f}: {got['markdown'][:60]!r}")
        worst = got["backed"] if worst is None else min(worst, got["backed"])
    if worst is None:
        raise Skip("no pane of that frame read as a document either way")
    return True, (f"a real note {real['backed']:.2f}, the stream's overlay "
                  f"{worst:.2f}")


@check("capture: steps over a patch the file cannot decode")
def _capture_damaged():
    """5.6GB of H264 is not always whole, and one bad patch is not a dead run.

    At 00:45:00 of the St. Jude replay ffmpeg reports "Error splitting the
    input into NAL units", exits 0 and writes no frames. 2:12:59 of the same
    file reads perfectly, so it is the recording, not this program -- but the
    run used to die on it and return nothing for six hours of video.
    """
    out_dir = machine.here(f"/mnt/g/Images/{VIDEOS['stjude']}")
    path, how = capture.capture_moment(video("stjude"), "00:45:00", out_dir)
    img = cv2.imread(path)
    if img is None:
        return False, "came back with no picture at all"
    if "moved" not in how:
        return False, f"decoded 00:45:00 without stepping over anything: {how}"
    return True, how


@check("chat: a speaker's name is a word")
def _chat_name_is_a_word():
    """The Finder sidebar read as a log, twice over.

    Its icons come back as "C)" and "e}" in their own colour at the margin,
    which is exactly the shape of an avatar and a name, so "Recents Shared
    Applications Pictures Movies Desktop Documents Downloads iCloud Drive"
    was reported as something a person said.
    """
    for pane in regions("memfiles", "00:00:00"):
        got = chat_reader.read_chat(pane, engine=engine())
        if got.get("is_chat"):
            who = [e["who"] for e in got["entries"]]
            return False, (f"{os.path.basename(pane)} read as a log by "
                           f"{who}")
    logs = [g for g in (chat_reader.read_chat(p, engine=engine())
                        for p in regions("july6", "00:40:36"))
            if g.get("is_chat")]
    if not logs:
        return False, "the real log stopped reading as one"
    return True, (f"the sidebar is not a log; the real one still reads "
                  f"{max(len(g['entries']) for g in logs)} entries")


@check("columns: a toolbar is not a heading row")
def _toolbar_not_heading():
    """A second Finder window, in another video, on a busier desktop.

    Its toolbar puts "vault-demo" across one band and "000" across another,
    and being the topmost row of the block it became the table's headings --
    with "Name / Date Modified / Size / Kind" demoted to the first row of data.
    The heading row is the first that names EVERY column, where a row does.
    """
    want = ("name", "date", "size", "kind")
    for pane in regions("memfiles", "00:00:00"):
        got = columns.read_list(pane)
        if not got.get("is_list"):
            continue
        for b in got["blocks"]:
            head = [c.lower() for c in b["header"]]
            if all(any(w in c for c in head) for w in want):
                return True, (f"{len(b['rows'])} rows under "
                              + " / ".join(b["header"]))
    return False, ("no block of that frame is headed by the window's four "
                   "column names")


@check("confirmation: a letter the other engine cannot make is never backed")
def _confirm_foreign():
    """The second engine is run with English only, so a Chinese character is
    one it can never confirm. The comparison comes down to letters and digits,
    which made the odd one invisible, and a terminal's title bar came back as
    confirmed reading "test-<CJK>Greeting and conversation start". A star drawn
    on a card is a symbol, not an alphabet, and is left alone."""
    got = dict(verify_names.confirm_readings(
        frame("obsidian", "00:02:09"),
        ["test-米Greeting and conversation start", "salt jewelry ★ 2k"],
        other_text="test-Greeting and conversation start salt jewelry 2k"))
    if got["test-米Greeting and conversation start"]:
        return False, "a reading carrying a Chinese character came back backed"
    if not got["salt jewelry ★ 2k"]:
        return False, "a drawn star cost a reading its backing; it is a symbol"
    return True, "the foreign letter is unbacked, the star is not"


@check("sweep: its own six marks all fire")
def _sweep_detectors():
    """A clean sweep means nothing if the thing reading it has gone deaf.

    `sweep.py` runs the pipeline over the library and reads the output back
    for the marks a fault leaves behind. Those marks are code like any other,
    and a sweep that reports nothing looks exactly the same whether the
    library is clean or the reader is broken. So each is shown a line it must
    catch, taken from output this build really produced.
    """
    import sweep
    sample = """--- 00:01:00  (stacked; interface on 90% of the frame) ---
  [pane 0: a terminal]
    aaa   <- the other engine read 'bbb'
    ccc   <- the other engine read 'ddd'
    eee   <- the other engine read 'fff'
    ggg
  [pane 1: a list of columns]
    | Jun27,2026at6:11PM      | 5KBLogFile |
  [pane 2: an open document]
    ---
    TYPING: IT YOURSELF
    ---
  [pane 3: text, not a tree]
    JK | N4 | U衣+ECE | 5D
--- 00:02:00  (stacked; interface on 80% of the frame) ---
    [this reader fell over and the run went on -- chat reader: TypeError: x]
"""
    got = {kind for kind, _ in sweep.smells(sample)}
    want = {"fell over", "data heading", "odd script", "all unsettled",
            "empty frame", "bare fences"}
    if got != want:
        missing = want - got
        return False, (f"{sorted(missing)} did not fire" if missing
                       else f"fired unasked: {sorted(got - want)}")
    return True, f"all six fire: {', '.join(sorted(want))}"


@check("pipeline: no pane is dropped for being short")
def _nothing_dropped():
    """Silent loss is the worst kind, because the answer still looks whole.

    This slide is nine cards in a three-column grid. The frame splits into
    three regions, and the left one holds three cards -- three readings, one
    short of the four a pane used to need before it was allowed to say
    anything. So "moonstone.co", "the tiny gem" and "hearthstone" were not in
    the answer, and nothing anywhere said a pane had been thrown away.
    """
    import subprocess
    r = subprocess.run([sys.executable, "pipeline.py", video("skills"),
                        "--at", "00:01:30"],
                       capture_output=True, text=True, encoding="utf-8")
    text = (r.stdout or "").lower()
    missing = [w for w in ("moonstone", "tiny gem", "hearthstone")
               if w not in text]
    if missing:
        return False, ("the whole frame's answer never mentions "
                       + ", ".join(missing) + "; three cards of nine")
    return True, "all three columns of the grid reach the answer"


@check("document: a line set in numbers is not a heading")
def _digits_are_not_a_heading():
    md = note_on("obsidian", "00:08:15", "OTT census")
    for line in md.splitlines():
        if "OTT census" in line and line.lstrip().startswith("#"):
            return False, ("'zero status data. OTT census: 6,285 active ...' "
                           "came back as a heading; it is the middle of a "
                           "paragraph, and only its digits are drawn tall")
    heads = [ln for ln in md.splitlines() if ln.lstrip().startswith("#")]
    if len(heads) < 3:
        return False, (f"only {len(heads)} headings left in a note that has "
                       "four; the size measure has stopped seeing them")
    if not any("Index" in ln for ln in heads):
        return False, "the note's 'Index' heading lost its rank"
    return True, (f"{len(heads)} real headings kept, the numbered lines left "
                  "in the prose where they were written")


@check("document: a mark in the gutter does not lose the line")
def _gutter_keeps_the_line():
    md = note_on("obsidian", "00:08:15", "Mailchimp blob")
    if "late-night pessimism" not in md:
        return False, ("the line 'tv folder\") flipped my late-night "
                       "pessimism: LTV ~$250 ...' is not in the reading; one "
                       "stray glyph in the gutter took the whole line with it")
    return True, "the line whose first glyph fell outside the column is in"


@check("capture: the burst median never holds the whole film at once")
def _median_stack():
    rng = np.random.default_rng(7)
    for n in (3, 4, 12, 45):
        frames = [rng.integers(0, 256, (48, 32, 3), dtype=np.uint8)
                  for _ in range(n)]
        want = np.median(np.stack(frames).astype(np.float32),
                         axis=0).astype(np.uint8)
        if not np.array_equal(want, capture._median_stack(frames)):
            return False, (f"a burst of {n} frames now stacks to a different "
                           "picture than it used to")
    if capture.BAND_ROWS > 512:
        return False, (f"a band of {capture.BAND_ROWS} rows is most of a "
                       "frame; the whole point is a bounded working set")
    return True, ("odd and even bursts stack to the same picture as the "
                  f"float32 median did, {capture.BAND_ROWS} rows at a time")


@check("pipeline: a caption is reported once, not as a tree as well")
def _drawn_once():
    caption = {"Everything dollar we make on",
               "live tonight is going to St. Jude's",
               "Children's Hospital and I am",
               "maching it! Give 10,000+ for",
               "a huge surprise. 1,000 plus for",
               "a light show."}
    for pane in regions("july31", "03:18:00"):
        tree = tree_reader.read_tree(pane)
        names = [r["name"] for r in tree.get("rows") or []]
        if not any("St. Jude" in n or "light show" in n for n in names):
            continue
        if not tree.get("is_tree"):
            return True, "the caption pane is not taken for a tree at all"
        if not pipeline.already_drawn(names, caption):
            return False, ("the caption came back as a file tree, and the "
                           "overlay it had already been proved to be did not "
                           "hold it back")
        return True, (f"{len(names)} caption lines taken for a tree, held back "
                      "as text this frame already reported drawn")
    raise Skip("no pane of the July 31 stream carries the caption")


@check("confirmation: a confirmed line keeps the spaces it was written with")
def _respaced():
    """The pane nothing could place is the commonest kind, and it read worst.

    Its engine is the better reader of short labels and the worse reader of
    running prose, where it drops the spaces. A sales page came back as
    "Youenteryouremailandyourcard." while the other engine, on the same
    pixels, had "You enter your email and your card." OCR drops spaces and
    never invents them, so the reading that has them saw them.
    """
    for pane in regions("post", "00:06:30"):
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401  (engine cached)
        res, _ = engine()(pane)
        texts = [t for _, t, _ in (res or [])]
        if not any("enteryouremail" in t.replace(" ", "").lower()
                   for t in texts):
            continue
        got = verify_names.confirm_readings(pane, texts[:16])
        said = [t for t, _ in got]
        want = "You enter your email and your card."
        if want not in said:
            return False, (f"the line came back as {[t for t in said if 'enter' in t.lower()]}, "
                           f"not {want!r}")
        run_on = [t for t in said if len(t) > 24 and " " not in t]
        return True, (f"respaced to {want!r}; "
                      f"{len(run_on)} line(s) still run together, and those "
                      "are the ones the other engine did not confirm")
    raise Skip("no pane of that frame carries the sign-up text")


@check("document: chrome scraps do not outvote paragraphs")
def _scraps_do_not_outvote():
    """A page of confirmed prose is not refused by the scraps around it.

    Counted one row per vote, `4 :` and `d5 560 ()1 31` weigh what a whole
    paragraph weighs. This page came to 0.64 against a gate of 0.67, fell out
    of the document reader by three hundredths, and came back as run-together
    loose text with its paragraphs and headings gone. By text it is 0.79.
    """
    for pane in regions("post", "00:02:10"):
        got = note_reader.read_note(pane)
        if "No fluff" not in got["markdown"]:
            continue
        if got["backed"] < note_reader.BACKED:
            return False, (f"the page reads {got['backed']:.2f} backed against "
                           f"a gate of {note_reader.BACKED:.2f}; every "
                           "paragraph on it was confirmed twice")
        spaced = [ln for ln in got["markdown"].splitlines()
                  if "No fluff. No theory" in ln]
        if not spaced:
            return False, "the prose came back without its spaces"
        return True, (f"{got['backed']:.2f} backed by text where it was 0.64 "
                      "by row, and the paragraphs keep their spacing")
    raise Skip("no pane of that frame carries the post")


@check("document: a joined paragraph is worth what its lines were worth")
def _joined_paragraph_verdict():
    """A wrapped paragraph carries every line's verdict, not just the first's.

    Lines are reconciled while they are still separate and joined afterwards,
    and the joined row can only hold one status -- the opening line's. So a
    700-character paragraph whose first line the two engines differed on
    counted as wholly unconfirmed, though seven of its eight lines were
    confirmed, and it dragged a daily note out of the document reader
    altogether: 0.64 against a gate of 0.67. Counting each line's own verdict
    in its own characters puts the same note at 0.74.
    """
    md = note_on("obsidian", "00:08:15", "Mailchimp blob")
    if "OTT census" not in md:
        return False, "the note came back without the paragraph in question"
    for pane in regions("obsidian", "00:08:15"):
        got = note_reader.read_note(pane)
        if "Mailchimp blob" not in got["markdown"]:
            continue
        if got["backed"] < note_reader.BACKED:
            return False, (f"the note reads {got['backed']:.2f} backed against "
                           f"a gate of {note_reader.BACKED:.2f}, so it is not "
                           "a document at all any more")
        return True, (f"{got['backed']:.2f} backed, where one paragraph's "
                      "opening line alone put it at 0.64")
    raise Skip("no pane of that frame carries the daily note")


@check("pipeline: every pane is accounted for, the empty ones too")
def _every_pane_speaks():
    """A frame's report must name every region the splitter found.

    Measured on a Facebook-ads frame: seven regions, three of them carrying
    everything and four carrying no text at all -- and those four printed
    nothing whatever, so the report gave a reader no way to tell a pane that
    held nothing from a pane that was never looked at. No text was lost by it;
    the claim was.
    """
    path = frame("works", "00:07:29")
    img = cv2.imread(path)
    boxes = panes.frame_regions(img, engine=engine())
    if len(boxes) < 3:
        raise Skip(f"only {len(boxes)} regions on this frame to account for")
    out = subprocess.run(
        [sys.executable, "pipeline.py", video("works"), "--at", "00:07:29"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=os.path.dirname(os.path.abspath(__file__)))
    said = out.stdout or ""
    named = set()
    for m in re.finditer(r"\[panes? ([\d, ]+):", said):
        named.update(int(v) for v in m.group(1).replace(" ", "").split(","))
    missing = [i for i in range(len(boxes)) if i not in named]
    if missing:
        return False, (f"{len(boxes)} regions were cut and panes {missing} are "
                       "in the report under no heading at all")
    return True, (f"all {len(boxes)} panes named; "
                  f"{len(re.findall('nothing readable on them', said))} line(s) "
                  "for the quiet ones")


@check("pipeline: a zoomed screen's own text is never called moving video")
def _no_zone_on_moving_capture():
    """A recording that zooms or pans moves its SCREEN, so motion stops
    meaning camera there. At 00:05:36 the works video is zoomed into a
    Finder window whose folder names sit behind censor bars; the one
    readable name is screen text, and it came back labelled "over moving
    video" before the guard. On a moment the capture itself caught moving,
    nothing may be claimed."""
    out = subprocess.run([sys.executable, "pipeline.py", video("works"),
                          "--at", "00:05:36"],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace",
                         cwd=os.path.dirname(os.path.abspath(__file__)))
    said = out.stdout or ""
    if "moving frames" not in said:
        raise Skip("00:05:36 no longer captures as a moving moment")
    if "sit over moving video" in said:
        return False, ("a moment the capture caught moving still claimed "
                       "words over moving video")
    if "Documents-test" not in said.replace(" ", ""):
        return False, "the folder name fell out of the report entirely"
    return True, "the zoomed Finder keeps its folder name, nothing claimed"


def pipeline_says(key, stamps):
    out = subprocess.run(
        [sys.executable, "pipeline.py", video(key), "--at", stamps],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=os.path.dirname(os.path.abspath(__file__)))
    return out.stdout or ""


@check("assembly: the screen speaks in windows, placed")
def _assembled_record():
    """The report reads as the screen, not as a bag of numbered panes.

    The desktop at 00:07:29 holds two drawn windows. Each pane the splitter
    cut inside one must be said UNDER it -- nested, with where it sits --
    and the window's own header must carry its place and its rectangle,
    because the words are the courtesy and the numbers are the layout. What
    belongs to no window is placed on the screen itself.
    """
    said = pipeline_says("works", "00:07:29")
    if not re.search(r"\n  \[window -- .+, \d+,\d+ to \d+,\d+", said):
        return False, "no window header carries a place and a rectangle"
    if not re.search(r"\n    \[pane \d+: .+ -- ", said):
        return False, "no pane is nested under a window with its place"
    if not re.search(r"\n  \[pane \d+: .+ -- ", said):
        return False, ("no loose pane is placed on the screen itself; "
                       "the menu strip should be")
    return True, "windows head their panes, and every reading has a place"


@check("assembly: a panel that is a window is said once, a lone panel still speaks")
def _panel_window_once():
    """A thing is said once, in its stronger form.

    At 00:01:52 the Finder over the video is found twice -- as a floating
    panel and as a drawn window whose panes were cut and read. The record
    must carry it ONCE, as the window, marked drawn over the picture; its
    raw dump said the same words the structured readings say better. And at
    00:03:44 the terminal panel has no panes behind it, so its own block is
    the only record there is -- it must still speak.
    """
    said = pipeline_says("works", "00:01:52,00:03:44")
    first, _, second = said.partition("--- 00:03:44")
    if "[a panel drawn on the picture]" in first:
        return False, ("00:01:52 still carries the raw panel dump beside "
                       "the window's own readings")
    if "drawn over the moving picture" not in first:
        return False, "the merged window is not marked drawn over the picture"
    if "CLAUDE.md" not in first:
        return False, "the Finder table's own reading fell out with the dump"
    if "zsh" not in second:
        return False, ("the lone terminal panel at 00:03:44 lost its only "
                       "record")
    return True, ("the Finder is said once as a window; the lone panel "
                  "keeps its block")


@check("assembly: no windows found, and the panes still land placed")
def _placed_without_windows():
    """Placement must not depend on the window finder having a good day.

    On this 1080p desktop the window finder returns nothing at all --
    measured, not assumed -- and the record must degrade to placed, flat
    panes: no window headers invented, every pane still saying where on the
    screen it sits.
    """
    said = pipeline_says("obsidian", "00:02:09")
    if "[window --" in said:
        raise Skip("the window finder now sees windows here; "
                   "pick a windowless frame to pin the degrade case")
    labels = re.findall(r"\[pane \d+: [^\]]+\]", said)
    if not labels:
        return False, "no pane labels in the report at all"
    unplaced = [x for x in labels if " -- " not in x]
    if unplaced:
        return False, f"panes with no place on the screen: {unplaced[:3]}"
    return True, f"{len(labels)} panes, each placed, no window invented"


@check("size: what is drawn large says so")
def _drawn_large():
    """Size is layout: the stream's banner is the reading a person calls
    large without thinking, and across stored panes what deserves the mark
    sits at 2.2x the pane's median glyph height and up, where body text
    tops out at 1.5. The record must carry the mark -- and only from
    measurement plus both engines' agreement, which is why a 1.8x slide
    title deliberately goes unmarked."""
    path = machine.here(
        "/mnt/g/Images/How I Trained My AI To Stop Making Mistakes/"
        "00-00-46_pane3.png")
    if not os.path.exists(path):
        path = machine.here(
            "/mnt/g/Images/How I Trained My AI To Stop Making Mistakes/"
            "Images/00-00-46_pane3.png")
    if not os.path.exists(path):
        raise Skip("the stored banner pane is gone")
    rec = pipeline.say_pane(path, 0, engine())
    if rec is None:
        raise Skip("nothing readable on the stored banner pane any more")
    if rec["kind"] != "text, not a tree":
        raise Skip(f"the banner pane now reads as {rec['kind']}; the LARGE "
                   "mark lives in loose text by design")
    big = [ln for ln in rec["lines"] if ln.startswith("[drawn large] ")]
    if not big:
        return False, ("the stream's banner is the largest thing on this "
                       "pane and carries no mark")
    if "jaredrhod" not in big[0]:
        return False, f"the large line is not the banner: {big[0][:80]}"
    return True, f"marked large: {big[0][len('[drawn large] '):][:60]}"


@check("assembly: the windows seen reach the end of the run")
def _windows_index():
    """A program's name reaches the record through what its window wrote
    across its own top -- "test" on the Finder, a terminal's own title line
    -- collected once at the end of the run with the moments it was seen.
    The 4K menu bar never became readable to either engine; this is the
    honest route around it."""
    said = pipeline_says("works", "00:01:52,00:03:44")
    if "[windows seen in this video]" not in said:
        return False, "no windows index at the end of the run"
    tail = said.split("[windows seen in this video]")[-1]
    if "test" not in tail or "00:01:52" not in tail:
        return False, f"the Finder's own word is not in the index: {tail[:120]}"
    return True, "the index carries the window's words and its moment"


@check("assembly: what did not change is not read twice")
def _reuse_unchanged():
    """Two stacked captures of the same screen one second apart differ by
    NOTHING on a still pane -- measured: not one pixel beyond the 8-grey
    compression bound on seven of eight panes, largest step 3. Those panes
    must be said from the previous moment's reading, marked so, with the
    readings carried whole -- and the pane where something moved must be
    read afresh. The rule is zero pixels over the bound: a cursor's worth
    of change could as easily be a digit's worth."""
    said = pipeline_says("works", "00:07:29,00:07:30")
    marks = said.count("unchanged since 00:07:29")
    if marks < 4:
        return False, (f"only {marks} pane(s) reused between two captures "
                       "of the same still screen")
    second = said.partition("--- 00:07:30")[2]
    if "MEMORY.md" not in second:
        return False, "the reused table lost its rows at the second moment"
    return True, f"{marks} panes reused, the readings carried whole"


@check("assembly: what appeared in a standing window is said as newly readable")
def _newly_readable():
    """Chronological understanding, first claim: a window standing in the
    same place read at two moments says which confirmed words the second
    look holds that the first did not. The claim is exactly that much --
    newly READABLE -- true whether Jared typed them or they merely became
    legible; which of the two is not measured, so it is not said. The
    specimen is the works terminal: bare prompt at one look, the typed
    path at the next."""
    said = pipeline_says("works", "00:02:50,00:03:50")
    if "newly readable since 00:02:50" not in said:
        return False, ("the second look at the standing terminal window "
                       "claims nothing newly readable")
    line = [ln for ln in said.splitlines()
            if "newly readable since 00:02:50" in ln][0]
    if "test" not in line:
        return False, f"the typed path is not among the new words: {line[:120]}"
    return True, "the typed command surfaces as newly readable, nothing more claimed"


@check("say_pane: a camera pane skips the structural readers, and loses nothing")
def _camera_pane_gate():
    """The cascade is skipped only when BOTH instruments came up empty:
    the tie test called the pane camera AND the recogniser read nothing.
    Either alone was tried and failed -- see say_pane for the story. So
    three legs, on one stream frame: the both-quiet pane skips (physical
    proof: no reader wrote its 3x enlargement), the camera-ties pane that
    CARRIES text still takes the full cascade, and the rendered pane
    takes it too."""
    img = cv2.imread(frame("qna", "00:02:00"))
    work = screenness.to_working_size(img)
    ties = screenness.tie_map(work).astype(np.float32)
    g_rows, g_cols = screenness.GRID
    bh = max(8, work.shape[0] // g_rows)
    bw = max(8, work.shape[1] // g_cols)
    sc = work.shape[1] / img.shape[1]

    def hits(b):
        return pipeline.rendered_here(
            ties, tuple(int(v * sc) for v in b), bh, bw)

    boxes = [tuple(int(v) for v in b)
             for b in panes.frame_regions(img, engine=engine())]
    base = frame("qna", "00:02:00").replace(".png", "")

    def cut_pane(tag, box):
        cut = f"{base}_{tag}.png"
        for side in (cut.replace(".png", "_3x.png"),
                     cut.replace(".png", "_3x_tess.png")):
            if os.path.exists(side):
                os.remove(side)
        if panes.write_box(img, box, cut) is None:
            return None
        return cut

    # the three legs of the rule: BOTH quiet -> skip; either speaks -> read
    empty_cam = texty_cam = rendered = None
    for i, b in enumerate(boxes):
        cut = cut_pane(f"gate{i}", b)
        if cut is None:
            continue
        res, _ = engine()(cut)
        n = len(res or [])
        if hits(b):
            rendered = rendered or (cut, b)
        elif n == 0:
            empty_cam = empty_cam or (cut, b)
        else:
            texty_cam = texty_cam or (cut, b)
    if not (empty_cam and texty_cam and rendered):
        raise Skip("this frame no longer holds all three pane kinds")

    rec0 = pipeline.say_pane(empty_cam[0], 0, engine(), (), None,
                             in_ui=False)
    if os.path.exists(empty_cam[0].replace(".png", "_3x.png")):
        return False, ("a structural reader ran on the empty camera "
                       "pane; its enlargement exists")
    if rec0 is not None and rec0["lines"]:
        return False, "the empty camera pane produced readings from nothing"
    rec1 = pipeline.say_pane(texty_cam[0], 1, engine(), (), None,
                             in_ui=False)
    kinds = ("a file tree", "a terminal", "a list of columns",
             "a chat log", "an open document")
    if not (rec1 is not None and rec1["kind"] in kinds) \
            and not os.path.exists(texty_cam[0].replace(".png", "_3x.png")):
        return False, ("the camera pane WITH text skipped the cascade -- "
                       "one instrument alone may never excuse a pane")
    rec2 = pipeline.say_pane(rendered[0], 2, engine(), (), None,
                             in_ui=True)
    if not (rec2 is not None and rec2["kind"] in kinds) \
            and not os.path.exists(rendered[0].replace(".png", "_3x.png")):
        return False, ("the rendered pane skipped the cascade; no reader "
                       "wrote its enlargement and none claimed it")
    return True, ("both-quiet pane skipped, text-bearing camera pane and "
                  "rendered pane both took the cascade")


@check("readers: the same pixels are never read twice")
def _memo_identical():
    """Three readers enlarge the same pane the same way and hand the same
    pixels to the same engines. The memo returns the FIRST reading for
    every repeat -- identical by construction, keyed on the bytes -- and a
    second full read of one pane must land at least one hit on each
    engine's memo. The two readings must also be equal and distinct
    objects, because callers mark up what they get."""
    cuts = regions("works", "00:07:29")
    if not cuts:
        raise Skip("no panes cut from the works desktop")
    pane = max(cuts, key=lambda p: os.path.getsize(p))
    rapid0, tess0 = tree_reader._MEMO_HITS, note_reader._TESS_HITS
    first = note_reader.read_note(pane)["markdown"]
    mid = note_reader._TESS_HITS
    again = note_reader.read_note(pane)["markdown"]
    a = tree_reader.ocr_rows(pane)
    b = tree_reader.ocr_rows(pane)
    if note_reader._TESS_HITS <= mid:
        return False, "a second read of the same pane reran tesseract"
    if tree_reader._MEMO_HITS <= rapid0:
        return False, "a second read of the same pane reran the recogniser"
    if first != again:
        return False, "the memo changed a reading between identical reads"
    if a != b or (a and a is b):
        return False, "the memo must hand back equal, distinct rows"
    return True, (f"rapid memo +{tree_reader._MEMO_HITS - rapid0}, "
                  f"tesseract memo +{note_reader._TESS_HITS - tess0} "
                  "on one pane read twice")


@check("assembly: an identical reading is said once, then pointed back to")
def _read_again_mark():
    """On a live stream the banner pane reads exactly the same at moment
    after moment -- same kind, same place, every line and mark identical.
    The record says it in full the first time and points back after:
    'read again: the same text as at ...'. A claim about the READING, not
    the pixels; video moves behind the banner, so the pixel carry cannot
    make it. The chat column's own content must still arrive in full at
    the first moment."""
    said = pipeline_says("qna", "00:14:20,00:14:30")
    first, _, second = said.partition("--- 00:14:30")
    if "jaredrhod.com" not in first:
        return False, "the banner's own line fell out of the first moment"
    if "read again: the same text as at 00:14:20" not in second:
        return False, ("the second identical reading was dumped again "
                       "instead of pointing back")
    if "x and grok" not in first:
        return False, "the chat column's content fell out of the first moment"
    return True, "identical reading said once, the second look points back"


@check("colour: named only where the ink is unmistakable")
def _color_marks():
    """Plain text measures saturation 0-25 and coloured text 68-153 with
    nothing between; the bound sits mid-gap at 45. Pinned on the ads
    manager pane, whose campaign links are drawn blue over a white table:
    the instrument names the link row blue and the plain row nothing;
    the document reader's own lines carry the mark behind the arrow; and
    a one-row cut that no reader claims brings the mark through the
    fallback as its own grouped line."""
    for pane in regions("post", "00:00:30"):
        rows = tree_reader.ocr_rows(pane)
        blue = next((r for r in rows if "Plan-2026" in r["text"]), None)
        plain = next((r for r in rows
                      if r["text"].strip().lower().startswith("daily")),
                     None)
        if blue and plain:
            break
    else:
        raise Skip("the ads pane no longer shows both row kinds")
    img = cv2.imread(pane)
    named = note_reader.row_ink_color(
        img, (blue["x0"], blue["y0"], blue["x1"], blue["y1"]))
    if named != "blue":
        return False, f"the campaign link row read {named!r}, not blue"
    if note_reader.row_ink_color(
            img, (plain["x0"], plain["y0"], plain["x1"],
                  plain["y1"])) is not None:
        return False, "a plain row was given a colour"
    md = note_reader.read_note(pane)["markdown"]
    if "<- drawn in blue" not in md:
        return False, "the document reader's lines carry no colour mark"
    cut = pane.replace(".png", "_colorrow.png")
    strip = img[max(0, blue["y0"] - 6):blue["y1"] + 6,
                max(0, blue["x0"] - 6):blue["x1"] + 6]
    cv2.imwrite(cut, strip)
    rec = pipeline.say_pane(cut, 0, engine(), (), None, in_ui=True)
    if rec is None or not any(ln.startswith("[drawn in blue]")
                              for ln in rec["lines"]):
        got = rec["lines"][:2] if rec else "nothing"
        return False, f"the fallback said {got} without the colour group"
    return True, ("link row blue, plain row unmarked, the mark arrives "
                  "through the document lines and the fallback both")


@check("records: the diary renders back from the records file, byte for byte, with the measurements beside it")
def _records_render():
    """Every run now keeps a records file beside its note: the exact
    characters printed per moment, and the measurements and reader
    structures those lines came from. A note is a rendering of its
    records, so the shape of the note can change without the video being
    read again. The proof that nothing said is lost: render.py's diary
    rendering of the records must equal the run's own output exactly --
    and the records must carry the data the drawing layer needs, not
    just the prose: a pane's box and reader structure, a window's
    rectangle and top words."""
    import render
    said = pipeline_says("memfiles", "00:03:00,00:04:10")
    path = machine.here(
        f"/mnt/g/Images/{VIDEOS['memfiles']}/records-at.jsonl")
    if not os.path.exists(path):
        return False, "the run wrote no records file"
    back = render.diary(path)
    if back != said:
        return False, (f"the rendering differs from the output: "
                       f"{len(back)} vs {len(said)} characters")
    moments = [e for e in render.entries(path) if e["kind"] == "moment"]
    if len(moments) != 2:
        return False, f"{len(moments)} moments recorded, not 2"
    m = moments[0]
    if not m["windows"] or "rect" not in m["windows"][0]:
        return False, "the Finder window at 00:03:00 carries no rectangle"
    panes = [p for p in m["panes"] if p.get("kind") == "a list of columns"]
    if not panes or not panes[0].get("data", {}).get("blocks"):
        return False, "the file list carries no reader structure"
    if not all("box" in p and "image" in p for p in m["panes"]):
        return False, "a pane lacks its box or its image"
    tree = [p for p in moments[1]["panes"] if p.get("kind") == "a file tree"]
    if not tree or not tree[0]["data"].get("rows"):
        return False, "the tree at 00:04:10 carries no rows"
    if "x0" not in tree[0]["data"]["rows"][0]:
        return False, "a tree row lacks its geometry"
    return True, (f"{len(said)} characters round-trip; {len(m['panes'])} panes "
                  f"with structure at 00:03:00, {len(tree[0]['data']['rows'])} "
                  "tree rows with geometry at 00:04:10")


@check("coverage: every recogniser reading on a pane is placed -- in the "
       "structure, beside it, or said unconfirmed -- and the counts prove it")
def _coverage():
    """The structural readers kept what fitted their structure and said
    nothing of the rest. Measured at 00:03:00 and 00:04:10 of the
    memory-files video: the Finder's toolbar title and Size header were
    dropped by the table reader and the 56 px title strip read nothing;
    the tree came back as 30 of 45 rows, broken at one cursor-jolted row;
    the note fell out of the document reader at 0.47 backed because every
    line a splitter cut read as junk past the cut, and the loose fallback
    then kept sixteen of its forty-three readings.

    Now: a second, taller title strip; a lattice fitted over the whole
    chain; an agreed-head rule for cut lines; the sixteen-reading cap
    gone; and a remainder rule -- what a reader leaves out is confirmed
    and said beside the structure, placed above, below or beside it. Each
    pane's record carries the count: readings, in the structure, beside
    it, unconfirmed, over video -- and they must add up, pane by pane."""
    import render
    said = pipeline_says("memfiles", "00:03:00,00:04:10")
    path = machine.here(
        f"/mnt/g/Images/{VIDEOS['memfiles']}/records-at.jsonl")
    moments = [e for e in render.entries(path) if e["kind"] == "moment"]
    if len(moments) != 2:
        return False, f"{len(moments)} moments recorded, not 2"
    for m in moments:
        for p in m["panes"]:
            c = (p.get("data") or {}).get("coverage")
            if not c:
                return False, f"pane {p['pi']} at {m['ts']} carries no coverage"
            total = c["in_structure"] + c["also"] + c["unconfirmed"] + c["video"]
            if total != c["readings"]:
                return False, (f"pane {p['pi']} at {m['ts']}: {c['readings']} "
                               f"readings, {total} placed")
    finder = moments[0]
    lst = [p for p in finder["panes"] if p["kind"] == "a list of columns"]
    if not lst:
        return False, "the file list was not read as a list"
    # The window the LIST was cut from, not whichever window the screen drew
    # first. A moment's windows are written in screen order, and this frame
    # holds a second Finder window at its left edge - half off the screen,
    # showing only its Size and Kind columns - so the window this asks about
    # is the second of the two.
    wi = lst[0].get("wi")
    win = next((w for w in (finder["windows"] or [])
                if w.get("wi") == wi), None)
    top = (win or {}).get("top") or ""
    if "Company A" not in top:
        return False, f"the Finder's title did not reach the header: {top!r}"
    rest = [r["text"] for r in lst[0]["data"].get("remainder") or []
            if r["confirmed"]]
    if not any("Size" in r for r in rest):
        return False, f"the Size header is not among the list's leftovers: {rest}"
    if not any("above the list] 02 Company A" in ln for ln in lst[0]["lines"]):
        return False, "the toolbar title is not said above the list"
    obsidian = moments[1]
    tree = [p for p in obsidian["panes"] if p["kind"] == "a file tree"]
    if not tree:
        return False, "the tree at 00:04:10 was not read as a tree"
    rows = tree[0]["data"]["rows"]
    if len(rows) < 45 or not rows[0]["name"].startswith("feedback_subject"):
        return False, (f"{len(rows)} tree rows, first {rows[0]['name']!r}; "
                       "45 from feedback_subject_line expected")
    doc = [p for p in obsidian["panes"] if p["kind"] == "an open document"]
    if not doc:
        return False, "the note at 00:04:10 was not read as a document"
    backed = doc[0]["data"]["backed"]
    if backed < 0.9:
        return False, f"the note is backed {backed:.2f}, under 0.9"
    if "so it can find anything:" not in said:
        return False, "the column clip still takes real words off a long line"
    strip = [p for p in finder["panes"] if p["pi"] == 0]
    if strip and strip[0]["kind"] == "an open document":
        return False, "the Finder's Size/Kind strip is claimed as a document"
    cov = [m["coverage"] for m in moments]
    return True, (f"00:03:00 {cov[0]['readings']} readings, {cov[0]['in_structure']} "
                  f"in structures, {cov[0]['also']} beside them, "
                  f"{cov[0]['unconfirmed']} unconfirmed; 00:04:10 "
                  f"{cov[1]['readings']} readings, {cov[1]['in_structure']} in "
                  f"structures, {cov[1]['also']} beside, {cov[1]['unconfirmed']} "
                  f"unconfirmed; tree {len(rows)} rows; note backed {backed:.2f}")


@check("style: what a pane looks like is measured and said -- dark or light, "
       "the band a row is drawn on, the marks before rows, the pictures, the "
       "words that lean, and where the pointer stood")
def _style():
    """The text readers say what is written; nothing said what it looked
    like. Tristan's own list of what the note must show: the window's
    furniture, a selected row, the dark or light look, italic and underline
    and links and the type, pictures and icons and the pointer. Measured on
    the memory-files video: the Finder's Dev row sits on a green band
    (45,137,68) on a (31,31,32) background; green folder marks stand before
    Assets, My Product and Operations; the pointer is at 1798,894 at
    00:03:00 and, half the size, at 319,929 at 00:04:10 -- on the very tree
    row the cursor had jolted; the one italic phrase on the note, "Every
    agent w", leans 9 degrees where upright words read under 5."""
    import render
    said = pipeline_says("memfiles", "00:03:00,00:04:10")
    path = machine.here(
        f"/mnt/g/Images/{VIDEOS['memfiles']}/records-at.jsonl")
    moments = [e for e in render.entries(path) if e["kind"] == "moment"]
    if len(moments) != 2:
        return False, f"{len(moments)} moments recorded, not 2"
    finder, obsidian = moments

    def near(found, x, y, slack=24):
        return found and abs(found["box"][0] - x) <= slack and abs(found["box"][1] - y) <= slack

    if not near(finder.get("pointer"), 1798, 894):
        return False, f"the pointer at 00:03:00 is not at 1798,894: {finder.get('pointer')}"
    if not near(obsidian.get("pointer"), 319, 929):
        return False, f"the pointer at 00:04:10 is not at 319,929: {obsidian.get('pointer')}"
    lst = [p for p in finder["panes"] if p["kind"] == "a list of columns"]
    if not lst:
        return False, "the file list was not read as a list"
    data = lst[0]["data"]
    look = (data.get("style") or {}).get("look") or {}
    if look.get("theme") != "dark":
        return False, f"the Finder list is not measured dark: {look}"
    styles = data["blocks"][0].get("row_style") or []
    rows = data["blocks"][0]["rows"]
    dev = [st for r, st in zip(rows, styles) if r and r[0].strip() == "Dev"]
    if not dev or dev[0].get("band") != "green":
        return False, f"the Dev row carries no green band: {dev}"
    marks = sum(1 for st in styles if st.get("icon"))
    if marks < 3:
        return False, f"{marks} rows carry a mark before them; 3 folders expected at least"
    if "a green band under: Dev" not in said or "[dark look" not in said:
        return False, "the style line is not said in the output"
    doc = [p for p in obsidian["panes"] if p["kind"] == "an open document"]
    if not doc:
        return False, "the note at 00:04:10 was not read as a document"
    lean = [r for r in doc[0]["data"]["rows"] if r.get("italic")]
    if not any("Everyagentw" in w for r in lean for w in r["italic"]):
        return False, f"the italic phrase was not found: {[r.get('italic') for r in lean]}"
    if "*Everyagentw*" not in said:
        return False, "the leaning word is not marked in the document's lines"
    fam = (doc[0]["data"].get("style") or {}).get("family")
    if fam != "proportional":
        return False, f"the note's type measured {fam!r}, not proportional"
    return True, (f"pointer at {finder['pointer']['box'][:2]} and {obsidian['pointer']['box'][:2]}; "
                  f"Dev on a green band; {marks} rows with marks; italic {lean[0]['italic']}; "
                  f"{fam} type; {look['theme']} look")


# -------------------------------------------- the windows the screen cuts off

@check("big windows: the two the screen cuts off are measured")
def _bigwin_measured():
    """`shapes` closes a window from two sides plus a top and a foot, and
    offers the frame's edge as a stand-in SIDE but never as a stand-in FOOT.
    So the browser and the Obsidian editor at this moment -- top and left
    edges drawn plainly, right and foot on the screen's own boundary -- were
    never measured at all, and the picture missed the two LARGEST windows on
    screen. These numbers are the frame's own pixels, measured by hand off
    00:00:00 before the finder was written."""
    import bigwin
    path = frame("memfiles", "00:00:00")
    got = bigwin.big_windows(path)
    want = {"the browser": (22, 65), "Obsidian": (77, 196)}
    if len(got) != 2:
        return False, "found %d big windows on a frame carrying 2" % len(got)
    im = cv2.imread(path)
    H, W = im.shape[:2]
    said = []
    for name, (wx, wy) in want.items():
        near = [b for b in got if abs(b[0] - wx) <= 6 and abs(b[1] - wy) <= 6]
        if not near:
            return False, "%s is not at (%d, %d); found %s" % (
                name, wx, wy, [(round(b[0]), round(b[1])) for b in got])
        b = near[0]
        if b[2] < W - 4 or b[3] < H - 4:
            return False, "%s does not run to the screen's own edges: %s" % (
                name, tuple(round(v) for v in b))
        said.append("%s at (%d, %d)" % (name, round(b[0]), round(b[1])))
    return True, "; ".join(said) + ", both cut off by the screen"


@check("big windows: the box stops at a real edge, not at the screen's")
def _bigwin_stops():
    """The one thing a box grown outward must never do. Painted over so the
    windows plainly END above the foot and left of the right edge, a finder
    that runs to the boundary anyway is measuring the screen, not a window."""
    import bigwin
    im = cv2.imread(frame("memfiles", "00:00:00"))
    H, W = im.shape[:2]
    out = os.path.join(os.path.dirname(frame("memfiles", "00:00:00")), "_check-bigwin")
    os.makedirs(out, exist_ok=True)
    said = []
    for label, cut in (("foot", "y"), ("right", "x")):
        a = im.copy()
        if cut == "y":
            a[1500:, :] = (12, 8, 14)
        else:
            a[:, 2600:] = (12, 8, 14)
        p = os.path.join(out, "cut-%s.png" % label)
        cv2.imwrite(p, a)
        shapes._CACHE.pop(p, None)
        bigwin._CACHE.pop((p, 0.20), None)
        got = bigwin.big_windows(p)
        if not got:
            return False, "found nothing on a frame still carrying two windows"
        far = max(b[3] for b in got) if cut == "y" else max(b[2] for b in got)
        edge = H if cut == "y" else W
        if far > edge - 200:
            return False, ("the %s edge came back at %d on a frame where the "
                           "windows end at %d" % (label, round(far),
                                                  1500 if cut == "y" else 2600))
        said.append("%s edge %d, not %d" % (label, round(far), edge))
    return True, "; ".join(said)


@check("big windows: a camera is not one, and neither is a panel")
def _bigwin_refuses():
    """A face is a field of round features and a hat brim makes a straight
    edge, so shape alone says window. And a flat card reaching the screen's
    edges with three round dots in its corner is a card, while a panel drawn
    inside a window is furniture. Each of these was a false window once."""
    import bigwin
    im = cv2.imread(frame("memfiles", "00:00:00"))
    H, W = im.shape[:2]
    out = os.path.join(os.path.dirname(frame("memfiles", "00:00:00")), "_check-bigwin")
    os.makedirs(out, exist_ok=True)

    face = cv2.resize(im[1152:2112, 0:1440], (W, H), interpolation=cv2.INTER_CUBIC)
    pf = os.path.join(out, "face.png")
    cv2.imwrite(pf, face)
    shapes._CACHE.pop(pf, None); bigwin._CACHE.pop((pf, 0.20), None)
    n_face = len(bigwin.big_windows(pf))
    if n_face:
        return False, "found %d windows on nothing but a camera" % n_face

    card = np.full((H, W, 3), (12, 8, 14), np.uint8)
    cv2.rectangle(card, (300, 240), (W - 1, H - 1), (45, 40, 38), -1)
    for i, c in enumerate(((70, 70, 200), (70, 190, 220), (90, 190, 90))):
        cv2.circle(card, (360 + i * 70, 300), 22, c, -1)
    cv2.rectangle(card, (700, 500), (2600, 1600), (30, 30, 30), -1)
    for i in range(3):
        cv2.circle(card, (760 + i * 70, 560), 22, (90, 90, 90), -1)
    pc = os.path.join(out, "panel.png")
    cv2.imwrite(pc, card)
    shapes._CACHE.pop(pc, None); bigwin._CACHE.pop((pc, 0.20), None)
    got = bigwin.big_windows(pc)
    if len(got) != 1:
        return False, ("the panel inside the window came back as a window too: "
                       "%d found where there is 1" % len(got))
    return True, "camera refused; the window kept and its panel refused"


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
