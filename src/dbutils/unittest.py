import sys
import os

def independence():
    # Simply check that dbutils can be imported.  This is run in a test flagged
    # as "local" since we want dbutils to be possible to import in standalone
    # unit tests.
    #
    # Hardly anything in dbutils can actually be used, of course, but that's not
    # a problem; the unit tests simply need to make sure not to depend on that.

    import dbutils

if __name__ == "__main__":
    # sys.path[0] is the directory containing this file.
    sys.path[0] = os.path.dirname(sys.path[0])

    if "independence" in sys.argv[1:]:
        independence()
