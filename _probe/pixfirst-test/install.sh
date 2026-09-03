#!/bin/bash
# Install a build as the master, then the vault copy.   install.sh <build number>
#
# The route: the master lives beside the video's images, and vault_sync.py writes
# the vault's copy into "04 - Resources/Dev/Jaredrhod/Sources/Screen Notes/" --
# the one home for screen notes. Nothing installs straight into the vault.
set -e
N="${1:?usage: install.sh <build number>}"
TOOL=/mnt/g/AI/Ethereal/ui-extractor
TITLE="Move Memory Files Out of Claude Code Into Obsidian"
B="$TOOL/_probe/note-cards$N.md"
M="/mnt/g/Images/$TITLE/$TITLE.md"
[ -s "$B" ] || { echo "no build note at $B"; exit 1; }
cp -f "$M" "$TOOL/_probe/master.pre-build$N.md"     # the build before it, kept
cp -f "$B" "$M"
echo "master: $(wc -c < "$M") bytes"
cd "$TOOL" && python3 vault_sync.py
V="/mnt/nas/obsidian-vault/04 - Resources/Dev/Jaredrhod/Sources/Screen Notes/$TITLE.md"
python3 -c "d=open(r'''$V''','rb').read(); print('vault copy:', len(d), 'bytes, nulls', d.count(b'\x00'))"
