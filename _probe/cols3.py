"""What read_list makes of each pane handed on the command line."""
import sys
import cv2

sys.path.insert(0, ".")
import columns

for path in sys.argv[1:]:
    got = columns.read_list(path)
    name = path.split("\\")[-1].split("/")[-1]
    if not got.get("is_list"):
        print(f"{name}: not a list ({got.get('why')})")
        continue
    print(f"{name}: {len(got['blocks'])} block(s)")
    for b in got["blocks"]:
        print(f"   {b['columns']} cols, {len(b['rows'])} rows, "
              f"bands {b['bands']}")
        print(f"   header: {b['header']}")
        if b["rows"]:
            print(f"   row 1 : {b['rows'][0]}")
