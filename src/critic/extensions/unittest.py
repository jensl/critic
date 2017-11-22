def independence():
    # Simply check that extensions can be imported.  This is run in a test
    # flagged as "local" since we want extensions to be possible to import in
    # standalone unit tests.
    #
    # Nothing in extensions can actually be used, of course, but that's not a
    # problem; the unit tests simply need to make sure not to depend on that.

    from critic import extensions

    print("independence: ok")
