def keepalives():
    # Run Repository.packKeepaliveRefs() and make sure it seems to do its job
    # correctly.  Since it's run as a nightly maintenance task, it would
    # otherwise not be exercised by testing.

    import api
    import gitutils

    critic = api.critic.startSession(for_testing=True)

    for repository in api.repository.fetchAll(critic):
        # Fetch the "internal" repository object.  This is a bit ugly, but we
        # can live with it in a test case.
        repository = repository._impl.getInternal(critic)

        # Make sure there's at least one loose keepalive ref.
        repository.keepalive(repository.revparse("HEAD"))

        loose_keepalive_refs_before = repository.run(
            "for-each-ref",
            "--format=%(objectname)",
            gitutils.KEEPALIVE_REF_PREFIX).splitlines()

        assert len(loose_keepalive_refs_before) > 0

        repository.packKeepaliveRefs()

        loose_keepalive_refs_after = repository.run(
            "for-each-ref",
            "--format=%(objectname)",
            gitutils.KEEPALIVE_REF_PREFIX).splitlines()

        assert len(loose_keepalive_refs_after) == 0

        chain_before = repository.revparse(gitutils.KEEPALIVE_REF_CHAIN)

        # Check that all previous loose keepalive refs are now ancestors of the
        # keepalive chain ref (IOW, are being kept alive by it.)
        for sha1 in loose_keepalive_refs_before:
            mergebase = repository.mergebase([sha1, chain_before])
            assert mergebase == sha1

        # Make sure there's a loose keepalive ref again.
        repository.keepalive(repository.revparse("HEAD"))
        repository.packKeepaliveRefs()

        chain_after = repository.revparse(gitutils.KEEPALIVE_REF_CHAIN)

        # Make sure the chain didn't change.
        assert chain_before == chain_after, ("%s != %s"
                                             % (chain_before, chain_after))

    print("keepalives: ok")
