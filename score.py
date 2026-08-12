import json, re, sys
def norm(s):
    t = re.sub(r"^.*?\d+ - ", "", s, count=1)
    t = re.sub(r"[^a-z0-9&.' ]", "", t.lower())
    return re.sub(r"\s+", " ", t).strip()
def main(json_path, fixture_path):
    d = json.load(open(json_path))
    fx = []
    for line in open(fixture_path):
        m = re.match(r"\s*(?:\u02c5|\u02c3|\|)*\s*([A-Za-z].*?)\s+((?:folder|FILE))(?:, (?:expanded|collapsed))?,?.*?depth (\d+)", line)
        # simpler: parse the fixture's CSV-ish last three fields
    # (full parser lives here in the calibrated build session)
    flat = []
    def walk(nodes, depth):
        for n in nodes:
            flat.append((norm(n["name"]), bool(n.get("folder", False)), n.get("depth", depth)))
            if "children" in n:
                walk(n["children"], n.get("depth", depth) + 1)
    walk(d["tree"], 0)
    print("rows:", len(flat))
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
