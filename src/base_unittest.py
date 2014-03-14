import sys

def independence():
    # Simply check that base can be imported.

    import base

if __name__ == "__main__":
    if "independence" in sys.argv[1:]:
        independence()
