import re, sys
sys.path.insert(0, '/home/trism/.claude/jobs/014c964f/tmp/replay')
import selfcheck as SC
L = open(sys.argv[1], encoding='utf-8').read().split('\n')
for ln in L:
    if not ln.startswith('<div class="sn-stage"'):
        continue
    st = re.search(r'sn-stamp">([^<]*)<', ln)
    print('===', st.group(1) if st else '?', '| deskbar' if 'sn-deskbar' in ln else '| no bar')
    tags = re.findall(r'class="sn-ghost-tag"[^>]*>([^<]*)<', ln)
    for k, (p, c) in enumerate(SC._boxes(ln, 'sn-ghost')):
        nm = tags[k] if k < len(tags) else '?'
        print("   outline  %-30s  l %5.1f  t %5.1f  w %5.1f  h %5.1f%s" %
              (nm[:30], p[0], p[1], p[2], p[3], '  (unsure)' if 'sn-away' in c else ''))
    for p, c in SC._boxes(ln, 'sn-slot'):
        print("   FILLED   %-30s  l %5.1f  t %5.1f  w %5.1f  h %5.1f" % ('', p[0], p[1], p[2], p[3]))
    for p, c in SC._boxes(ln, 'sn-camera'):
        print("   camera   %-30s  l %5.1f  t %5.1f  w %5.1f  h %5.1f" % ('', p[0], p[1], p[2], p[3]))
