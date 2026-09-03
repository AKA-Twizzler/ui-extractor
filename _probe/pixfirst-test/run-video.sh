#!/bin/bash
# Draw, gate and install ANY video's note.   run-video.sh "<video title>" [tag]
#
# WHY THIS EXISTS. build.sh and install.sh beside it carry
# TITLE="Move Memory Files Out of Claude Code Into Obsidian" hardcoded, which
# was right while one video was being perfected and is wrong the moment the
# second one starts: the job note's order is one video per element, ten of
# them, and a chain that has to be hand-rolled for nine of those is a chain
# with a step waiting to be skipped. This takes the title.
#
# It does NOT read the video. The read is `pipeline.py <video> --dense` and
# takes its own time; this is everything after it, in one command:
#     draw -> selfcheck -> verify_pictures -> verify_rows -> compare
#     -> install as the master -> sync the vault copy
#
# The tag names the build's own copy under _probe/ and nothing else; the
# master and the vault copy are named for the video, always.
set -u
TITLE="${1:?usage: run-video.sh \"<video title>\" [tag]}"
TAG="${2:-$(date +%m%d-%H%M)}"
TOOL=/mnt/g/AI/Ethereal/ui-extractor
D="/mnt/g/Images/$TITLE"
W="G:\\Images\\$TITLE"
# EVERY PATH HANDED TO THE WINDOWS PYTHON IS RELATIVE OR IN G:\ FORM.
# draw3.py, selfcheck.py and the two verifiers run on the Windows
# interpreter, which cannot see /mnt/... at all: an absolute WSL path gets it
# all the way through the work and then fails on the write, which is exactly
# what happened the first time this ran. B is relative to the tool; BW is the
# same file for the WSL-side commands.
B="_probe/note-$TAG.md"
BW="$TOOL/$B"
M="$D/$TITLE.md"
cd "$TOOL"

[ -s "$D/records.jsonl" ] || { echo "no records at $D/records.jsonl -- run the read first:"; \
  echo "  ./.venv/Scripts/python.exe pipeline.py \"<the mp4, in G:\\ form>\" --dense"; exit 1; }

echo "=== $TITLE  (tag $TAG) ==="

# A BUILD ALREADY GATED IS NOT REDRAWN. The draw is the expensive half and
# INSTALL=1 is normally a second call after the gates have been read, so
# without this the note is built twice to install it once. A note newer than
# the records it came from is the same note; anything else is redrawn.
if [ -s "$BW" ] && [ "$BW" -nt "$D/records.jsonl" ]; then
  echo "reusing the build at $B (newer than its records); not redrawing"
else
PF_WIN=${PF_WIN:-3} SN_PIXFIRST=1 SN_THUMBS=1 SN_ZOOM=1 SN_PITCH=1 SN_NAMES=1 \
  WSLENV=PF_WIN:SN_PIXFIRST:SN_THUMBS:SN_ZOOM:SN_PITCH:SN_NAMES \
  /home/trism/Ethereal/iogate.sh cards-draw ./.venv/Scripts/python.exe draw3.py \
  "$W\\records.jsonl" "$B"
echo "draw rc=$?"
fi
[ -s "$BW" ] || { echo "the draw produced nothing; stopping before the gates"; exit 1; }

# The two verifiers are handed the note in the Windows form build.sh uses --
# a backslash path relative to the tool -- because that is the one that has
# been proven, and a forward slash here would be a change nobody asked for.
REL="_probe\\$(basename "$B")"
echo "== selfcheck";        ./.venv/Scripts/python.exe selfcheck.py "$REL" 2>&1 | tail -5
echo "== verify_pictures";  ./.venv/Scripts/python.exe verify_pictures.py \
  "$REL" "$W\\Images" "$W\\records.jsonl" 2>&1 | tail -6
echo "== verify_rows";      ./.venv/Scripts/python.exe verify_rows.py \
  "$REL" "$W\\records.jsonl" 2>&1 | tail -4
echo "== compare";          rm -rf "_probe/cmp-$TAG"
/home/trism/Ethereal/iogate.sh cards-cmp python3 compare.py "$BW" "$D/Images" \
  "_probe/cmp-$TAG" 2>&1 | grep -v "^\[iogate"

# The gates have spoken; installing is a separate decision, so it is asked for.
if [ "${INSTALL:-0}" = "1" ]; then
  [ -f "$M" ] && cp -f "$M" "$TOOL/_probe/master.pre-$TAG.md"
  cp -f "$BW" "$M"
  echo "master: $(wc -c < "$M") bytes"
  python3 vault_sync.py
  V="/mnt/nas/obsidian-vault/04 - Resources/Dev/Jaredrhod/Sources/Screen Notes/$TITLE.md"
  python3 -c "d=open(r'''$V''','rb').read(); print('vault copy:', len(d), 'bytes, nulls', d.count(b'\x00'))"
else
  echo "NOT installed. Read the gates above, then re-run with INSTALL=1 to make it the master."
fi
echo "DONE $(date +%H:%M)"
