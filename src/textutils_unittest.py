import sys

def independence():
    # Simply check that textutils can be imported.

    import textutils

if __name__ == "__main__":
    if "independence" in sys.argv[1:]:
        independence()
