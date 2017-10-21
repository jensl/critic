def independence():
    # Simply check that dbutils can be imported.  This is run in a test flagged
    # as "local" since we want dbutils to be possible to import in standalone
    # unit tests.
    #
    # Hardly anything in dbutils can actually be used, of course, but that's not
    # a problem; the unit tests simply need to make sure not to depend on that.

    import dbutils

    print("independence: ok")
