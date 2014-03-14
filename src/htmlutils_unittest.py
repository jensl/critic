import sys

def independence():
    # Simply check that htmlutils can be imported.

    import htmlutils

if __name__ == "__main__":
    if "independence" in sys.argv[1:]:
        independence()
