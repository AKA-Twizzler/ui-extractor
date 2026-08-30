import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import note_reader as N
n = N.read_note(sys.argv[1])
print(n["markdown"])
