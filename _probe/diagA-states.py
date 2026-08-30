# diagA: what the drawing code sees for the Obsidian states (read only; calls furnish.obsidian in memory)
import sys, os, re
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import draw3, draw as old, draw2, furnish
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
draw3.harmonise(states)
for st in states:
    if st.name != "The Obsidian window":
        continue
    doc = st.main_doc(); tree = st.tree()
    print("=" * 70)
    print("STATE title=%r times=%s..%s (%d)" % (st.title, st.times[0], st.times[-1], len(st.times)))
    print(" times:", st.times)
    print(" rect:", getattr(st, "rect", None), "shape:", getattr(st, "shape", None), "theme:", getattr(st, "theme", None))
    print(" rects:", getattr(st, "rects", None))
    for q in getattr(st, "parts", []):
        print(" part:", {k: v for k, v in q.items() if k != "model"})
    print(" explorer_count:", getattr(st, "explorer_count", None), "_doc_wide:", getattr(st, "_doc_wide", None),
          "_doc_pad:", getattr(st, "_doc_pad", None), "_tree_fr:", getattr(st, "_tree_fr", None), "_tree_min:", getattr(st, "_tree_min", None))
    print(" topwords:", [(w[0], w[1], w[3]) for w in st.topwords][:14])
    try:
        ws = [w for w in st.words() if re.search(r"Add\s*property|Vault", w)]
        print(" words hit:", ws[:12])
    except Exception as e:
        print(" words() failed:", e)
    if tree:
        rows = [t for t, h in tree.lines]
        print(" tree rows:", len(rows), "longest:", max(len(r) for r in rows), repr(max(rows, key=len)))
    if doc:
        print(" doc.title():", repr(doc.title()), "kind:", getattr(doc, "kind", None), "blocks:", len(getattr(doc, "blocks", ()) or ()))
        for t, h in doc.lines[:12]:
            print("   line:", repr(t)[:90], "|| h:", h[:110])
    for m, g in getattr(st, "pieces", ()):
        docs = [q for q in (g.get("panes") or []) if q.get("kind") == "an open document"]
        if not docs:
            continue
        widest = max(docs, key=lambda q: q["box"][2] - q["box"][0])
        for p_ in docs:
            pw = p_["box"][2] - p_["box"][0]
            xs = [it["box"] for it in draw2.items_of(p_) if it["box"][2] - it["box"][0] > 20]
            if pw > 0 and len(xs) >= 3:
                span = max(b[2] for b in xs) - min(b[0] for b in xs)
                print("  piece", m["ts"], "doc pane", p_["box"], "items", len(xs), "xspan", min(b[0] for b in xs), max(b[2] for b in xs),
                      "span/pw=%.3f" % (span / pw), "<-- widest, counted" if p_ is widest else "")
    html = furnish.obsidian(st, behind=False)
    m_ = re.search(r'grid-template-columns: ([^"]+)"', html or "")
    print(" obsidian() grid:", m_.group(1) if m_ else None, "| _tree_min after:", getattr(st, "_tree_min", None))
    m_ = re.search(r'<div class="sn-doc"[^>]*>.{0,600}', html or "")
    print(" doc html head:", m_.group(0) if m_ else None)
