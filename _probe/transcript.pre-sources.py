#!/usr/bin/env python3
"""Put Jared's words back beside the screen he was showing when he said them.

    python3 transcript.py <video>

The two halves of a video are captured separately and neither is much use
alone. The screens say what was on the machine; the transcript says what was
being explained. A tree of folders with no words beside it is a list of names,
and a paragraph about "this folder here" with no tree beside it points at
nothing.

Both are stamped with the same clock, which is the whole join: the video map
already breaks the recording into stretches, one per distinct screen, each
with the second it starts and the second it ends; the transcript carries a
timestamp on every line. So the words belonging to a screen are the lines
whose stamp falls inside that screen's stretch. No matching of text to text,
no judgment about what a passage is "about" -- one clock, read twice.

Where the transcript for a video cannot be found it says so and returns
nothing, rather than joining a screen to somebody else's words.
"""
import os
import re
import sys
import machine

TRANSCRIPTS = machine.here("/mnt/nas/obsidian-vault/04 - Resources/Dev/"
                          "Jaredrhod/Transcripts MD")
STAMP = re.compile(r"^\*\*\[(\d+):(\d{2}):(\d{2})\]\*\*\s*(.*)$")


def title_of(video):
    """The video's title, which is the folder it lives in."""
    return os.path.basename(os.path.dirname(os.path.abspath(video)))


def find(title, folder=TRANSCRIPTS):
    """The transcript file for a title, or None.

    Three of the forty-three carry a trailing full stop the video folder does
    not ("...Here's How." against "...Here's How"), so the name is compared
    with trailing dots and spaces off both sides. Nothing looser than that:
    a near-match to the wrong video would attach the wrong words, which is
    worse than attaching none.
    """
    if not os.path.isdir(folder):
        return None

    def key(s):
        return s.strip().rstrip(". ").lower()

    want = key(title)
    for name in os.listdir(folder):
        if name.endswith(".md") and key(name[:-3]) == want:
            return os.path.join(folder, name)
    return None


def load(path):
    """Every stamped line of a transcript, as (second, words)."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = STAMP.match(line.strip())
            if not m:
                continue
            h, mi, s, text = m.groups()
            if text.strip():
                out.append((int(h) * 3600 + int(mi) * 60 + int(s),
                            text.strip()))
    out.sort()
    return out


def between(lines, start, end):
    """The words spoken while a screen was up.

    Where a screen was up too briefly to contain a whole caption line, it gets
    the line that was RUNNING when it appeared, so a screen shown for four
    seconds still says what was being said over it rather than nothing.
    """
    said = [text for t, text in lines if start <= t < end]
    if said:
        return " ".join(said).strip()
    running = [text for t, text in lines if t <= start]
    return running[-1] if running else ""


def words_for(video, runs):
    """Attach the transcript to each stretch of the video map.

    Pass EVERY stretch, in order, not only the ones showing a screen. A
    stretch ends at its own last sample, which is where the screen was last
    LOOKED at, not where it went away; the screen was up until the next
    stretch began. Measured against a stretch's own end, twenty of one
    video's twenty-three screens came back with a single caption line each,
    because the map had sampled them once.

    Returns the runs with a "said" on each, or None where there is no
    transcript to attach.
    """
    path = find(title_of(video))
    if path is None:
        return None
    lines = load(path)
    if not lines:
        return None
    for i, r in enumerate(runs):
        until = runs[i + 1]["start"] if i + 1 < len(runs) else r["end"] + 30
        r["until"] = until
        r["said"] = between(lines, r["start"], max(until, r["start"] + 1))
    return runs


def main():
    import spot
    video = sys.argv[1]
    every = (int(sys.argv[sys.argv.index("--every") + 1])
             if "--every" in sys.argv else 10)
    title = title_of(video)
    path = find(title)
    if path is None:
        print(f"NO TRANSCRIPT for {title!r} in {TRANSCRIPTS}")
        return 1
    cache = machine.here(f"/mnt/g/Images/{title}/scan.json")
    samples = spot.scan(video, every, cache)
    every_run = spot.stretches(samples)
    words_for(video, every_run)
    runs = [r for r in every_run if r["call"] == "screen"]
    print(f"=== {title} ===")
    print(f"{len(runs)} distinct screens, transcript {os.path.basename(path)}\n")
    for r in runs:
        said = r.get("said") or "(nothing said while this screen was up)"
        print(f"--- {spot.hms(r['start'])} to {spot.hms(r.get('until', r['end']))} ---")
        print(f"    {said}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
