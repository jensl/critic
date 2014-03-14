import sys
import os

def independence():
    # Simply check that operation can be imported.

    import operation

if __name__ == "__main__":
    # sys.path[0] is the directory containing this file.
    sys.path[0] = os.path.dirname(sys.path[0])

    if "independence" in sys.argv[1:]:
        independence()
