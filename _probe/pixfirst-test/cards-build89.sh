#!/bin/bash
cd /mnt/g/AI/Ethereal/ui-extractor
D="/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian"
PF_WIN=${PF_WIN:-3} SN_PIXFIRST=1 SN_THUMBS=1 SN_ZOOM=1 SN_PITCH=1 SN_NAMES=1 WSLENV=PF_WIN:SN_PIXFIRST:SN_THUMBS:SN_ZOOM:SN_PITCH:SN_NAMES /home/trism/Ethereal/iogate.sh cards-draw ./.venv/Scripts/python.exe draw3.py "G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl" _probe/note-cards89.md
echo "draw rc=$?"
./.venv/Scripts/python.exe selfcheck.py _probe/note-cards89.md 2>&1 | tail -5
echo "== verify_pictures"; ./.venv/Scripts/python.exe verify_pictures.py "_probe\note-cards89.md" "G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images" "G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl" 2>&1 | tail -6
echo "== verify_rows"; ./.venv/Scripts/python.exe verify_rows.py "_probe\note-cards89.md" "G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl" 2>&1 | tail -4
rm -rf _probe/cmp-cards89; /home/trism/Ethereal/iogate.sh cards-cmp python3 compare.py _probe/note-cards89.md "$D/Images" _probe/cmp-cards89 2>&1 | grep -v "^\[iogate" 
echo "CARDS BUILD DONE $(date +%H:%M)"
