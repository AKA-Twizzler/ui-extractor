#!/bin/bash
# shot.sh NAME SRC.md  -> renders and cuts strips into _probe/look/NAME_k.png
N=$1; SRC=$2
cd /home/trism/.claude/jobs/014c964f/tmp/replay-jobs/80eddce6/tmp/cov && python3 render.py $SRC /home/trism/.claude/jobs/014c964f/tmp/replay/_probe/look/$N.html >/dev/null && cd /home/trism/.claude/jobs/014c964f/tmp/replay/_probe/look && rm -f ${N}*.png; "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless --disable-gpu --hide-scrollbars --window-size=1100,12000 --screenshot="G:\\AI\\Ethereal\\ui-extractor\\_probe\\look\\$N.png" "file:///G:/AI/Ethereal/ui-extractor/_probe/look/$N.html" 2>/dev/null; python3 -c "
from PIL import Image
import numpy as np
im=Image.open('$N.png'); a=np.array(im.convert('L')); rows=np.where((a!=30).any(axis=1))[0]; h=rows.max()+20; n=(h+1799)//1800
for k in range(n): im.crop((0,k*1800,1100,min(h,(k+1)*1800))).save(f'${N}_{k}.png')
print(n, h)"
