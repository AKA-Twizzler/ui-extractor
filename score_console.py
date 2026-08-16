#!/usr/bin/env python3
"""Grade a terminal read against the ground-truth fixture.

The fixture is Tristan's own reading of the 00:02:42 frame and is the
definition of done. This prints the verdict as counts, so a change to the
reader is judged on evidence rather than on whether the output looks better,
and it names every line it got wrong.

Run: python3 score_console.py <frame.png>
"""
import difflib
import sys

import console_reader

TRUTH = [
    ("Next: Run claude --help to get started", False, False),
    ("⚠ Setup notes:", False, False),
    ("● Native installation exists but ~/.local/bin is not in your PATH.",
     False, "edge"),
    ("echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.zshrc && source",
     False, "cut"),
    ("✅ Installation complete!", False, False),
    ("[jared@macbook-air ~ % echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >>",
     True, "edge"),
    ("source ~/.zshrc", False, False),
    ("[jared@macbook-air ~ % cd ~/documents/henry", True, False),
    ("[jared@macbook-air henry %", True, False),
]


def whole(line):
    """The line as it stood on screen, prompt and all."""
    if line["kind"] == "typed" and line["prompt"]:
        return f"{line['prompt']} {line['text']}".strip()
    return line["text"].strip()


def main(png):
    res = console_reader.read_console(png)
    if not res.get("is_console"):
        print(f"NOT READ AS A TERMINAL - {res.get('why')}")
        return 1
    got = res["lines"]
    if len(got) != len(TRUTH):
        print(f"line count {len(got)}, expected {len(TRUTH)}")
    chars = right = 0
    kinds = cuts = 0
    for i, (want, typed, cut) in enumerate(TRUTH):
        line = got[i] if i < len(got) else {"kind": "output", "text": "",
                                            "prompt": None, "clipped": None}
        mine = whole(line)
        m = difflib.SequenceMatcher(None, want, mine)
        same = sum(b.size for b in m.get_matching_blocks())
        chars += len(want)
        right += same
        kinds += (line["kind"] == "typed") == typed
        cuts += (line["clipped"] or None) == (cut or None)
        if same < len(want) or (line["kind"] == "typed") != typed \
                or (line["clipped"] or None) != (cut or None):
            print(f"  line {i + 1}: {same}/{len(want)} characters"
                  f"{'' if (line['kind'] == 'typed') == typed else '  TYPED WRONG'}"
                  f"{'' if (line['clipped'] or None) == (cut or None) else '  CUT ' + str(line['clipped'])}")
            print(f"    want: {want}")
            print(f"    got : {mine}")
    print(f"\ncharacters {right}/{chars} ({100.0 * right / chars:.1f}%)   "
          f"typed-vs-output {kinds}/{len(TRUTH)}   "
          f"cut marks {cuts}/{len(TRUTH)}   "
          f"the font settled {res['fixed']} letters")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
