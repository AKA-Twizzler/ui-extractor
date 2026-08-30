import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3
LIVE = []
real_init = draw3.State.__init__
def init(self, group, ts):
    real_init(self, group, ts); LIVE.append(self)
draw3.State.__init__ = init
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
h1 = [(st.name, len(st._h1_read)) for st in LIVE if st._h1_read]
dw = [(st.name, len(st._doc_wide_at)) for st in LIVE if st._doc_wide_at]
pit = [(st.name, len(st._pitch_at)) for st in LIVE if st._pitch_at]
sd = sum(1 for st in LIVE for sn in st._seen.values() if sn.stood)
print("states built: %d" % len(LIVE))
print("  headings on the moment (_h1_read):   %d states, %d readings" % (len(h1), sum(n for _, n in h1)))
print("  note width on the moment:            %d states, %d readings" % (len(dw), sum(n for _, n in dw)))
print("  row pitch on the moment:             %d states, %d readings" % (len(pit), sum(n for _, n in pit)))
print("  where words stood, on the moment:    %d readings" % sd)
print("  rects on the moment:                 %d" % sum(len(st.rects) for st in LIVE))
print("  moments measured off the frame:      %d" % sum(len(st.measured) for st in LIVE))
