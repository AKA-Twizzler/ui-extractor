#!/bin/bash
# Install build 89's note as the vault copy: the note's own twelve-line header, then the build's body.
set -e
N="${1:-89}"
V="/mnt/nas/obsidian-vault/00 - Inbox/Tristan/For You - The Rebuilt Note - Move Memory Files.md"
B="/mnt/g/AI/Ethereal/ui-extractor/_probe/note-cards$N.md"
T=/home/trism/.claude/jobs/014c964f/tmp
head -12 "$V" > $T/install-note.md
cat "$B" >> $T/install-note.md
python3 /home/trism/Ethereal/vaultwrite/vaultwrite.py write "$V" < $T/install-note.md
echo "installed build $N: $(wc -c < "$V") bytes, nulls $(tr -cd '\000' < "$V" | wc -c), header intact: $(head -9 "$V" | grep -c 'For You - The Rebuilt Note')"
