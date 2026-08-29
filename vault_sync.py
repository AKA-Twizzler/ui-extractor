#!/usr/bin/env python3
"""Copy every finished video note into the vault's Screen Notes folder.

    python3 vault_sync.py          (WSL side -- the vault is not reachable
                                    from Windows, measured, so the sync runs
                                    where /mnt/nas is)

Beside Transcripts (what was said), Sources/Screen Notes holds what was on
screen: a synced copy of each video's chronological note, frontmatter added
per the vault's convention, the master staying beside the video's images.
A copy is rewritten only when the master is newer.
"""
import os
import sys

SRC = "/mnt/g/Images"
DST = ("/mnt/nas/obsidian-vault/04 - Resources/Dev/Jaredrhod/"
       "Sources/Screen Notes")      # the one home; "Screen Notes MD" was a duplicate, folded in


def main():
    os.makedirs(DST, exist_ok=True)
    synced = kept = 0
    for title in sorted(os.listdir(SRC)):
        if title.startswith("_"):
            continue
        master = os.path.join(SRC, title, f"{title}.md")
        if not os.path.exists(master):
            continue
        target = os.path.join(DST, f"{title}.md")
        if (os.path.exists(target)
                and os.path.getmtime(target) >= os.path.getmtime(master)):
            kept += 1
            continue
        body = open(master, encoding="utf-8").read().splitlines()
        head = [
            "---",
            "status: active",
            "project: vault",
            "type: reference",
            f"source: G:\\Images\\{title}\\{title}.md",
            "---",
            "",
        ]
        # a copy that already stands keeps its own front matter: some carry
        # the `screen-note` class the stylesheet widens the page for
        if os.path.exists(target):
            old_lines = open(target, encoding="utf-8").read().splitlines()
            if old_lines[:1] == ["---"] and "---" in old_lines[1:]:
                end = old_lines.index("---", 1)
                kept = old_lines[:end]
                # a kept front matter still names its master
                if not any(ln.startswith("source:") for ln in kept):
                    kept.append(f"source: G:\\Images\\{title}\\{title}.md")
                head = kept + ["---", ""]
        for i, ln in enumerate(body):
            if ln.startswith("# "):
                body.insert(i + 1, "")
                body.insert(i + 2,
                            "> Synced copy. The master lives beside the "
                            "video's images, at the source path above.")
                break
        text = "\n".join(head + body) + "\n"
        tmp = target + ".tmp-write"
        data = text.encode("utf-8")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
        back = open(target, "rb").read()
        assert back == data and back.count(b"\x00") == 0
        synced += 1
        print(f"  synced  {title}")
    print(f"{synced} synced, {kept} already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
