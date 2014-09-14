with repository.workcopy() as work, frontend.signin("alice"):
    REMOTE_URL = instance.repository_url("alice")

    def assert_branch_state(archived):
        # Check that the branch is or isn't flagged as archived on the review
        # front-page.
        document = frontend.page("r/1")
        basic = testing.expect.find_paleyellow(document, 0)
        branch = basic.find(attrs=testing.expect.with_class("branch"))
        actual = "archived" in branch["class"].split()
        testing.expect.check(archived, actual)
        branch_name = testing.expect.extract_text(branch)

        # Also check that the branch's ref exists or doesn't exist in the
        # repository.
        expected = "ref is missing" if archived else "ref is present"
        try:
            work.run(["ls-remote", "--exit-code", REMOTE_URL,
                      "refs/heads/" + branch_name])
            actual = "ref is present"
        except testing.repository.GitCommandError:
            actual = "ref is missing"
        testing.expect.check(expected, actual)

    # Check that the branch isn't already archived (no reason whatsoever it
    # should be.)
    assert_branch_state(archived=False)

    # Check that the operations fail as expected on an open review whose branch
    # is not already archived.
    frontend.operation(
        "archivebranch",
        data={ "review_id": 1 },
        expect={ "status": "failure",
                 "code": "invalidstate" })
    frontend.operation(
        "resurrectbranch",
        data={ "review_id": 1 },
        expect={ "status": "failure",
                 "code": "invalidstate" })

    # Drop the review, archive the branch, and check that it became archived.
    frontend.operation(
        "dropreview",
        data={ "review_id": 1 })
    frontend.operation(
        "archivebranch",
        data={ "review_id": 1 })
    assert_branch_state(archived=True)

    # Check that this operation now fails.
    frontend.operation(
        "archivebranch",
        data={ "review_id": 1 },
        expect={ "status": "failure",
                 "code": "invalidstate" })

    # Resurrect the branch and check that it becomes not archived again.
    frontend.operation(
        "resurrectbranch",
        data={ "review_id": 1 })
    assert_branch_state(archived=False)

    # Schedule an archival in -1 days (i.e. ASAP), force maintenance to run, and
    # check that the branch was archived.
    frontend.operation(
        "schedulebrancharchival",
        data={ "review_id": 1,
               "delay": -1 })
    assert_branch_state(archived=False)
    instance.synchronize_service("maintenance", force_maintenance=True)
    assert_branch_state(archived=True)

    # Resurrect branch again.
    frontend.operation(
        "resurrectbranch",
        data={ "review_id": 1 })
    assert_branch_state(archived=False)

    # Schedule an archival in 1 day (i.e. not now), force maintenance to run,
    # and check that the branch wasn't archived.
    frontend.operation(
        "schedulebrancharchival",
        data={ "review_id": 1,
               "delay": 1 })
    instance.synchronize_service("maintenance", force_maintenance=True)
    assert_branch_state(archived=False)

    # Schedule another archival in -1 days (i.e. ASAP), then reopen the review,
    # force maintenance to run, and check that the branch wasn't archived.
    frontend.operation(
        "schedulebrancharchival",
        data={ "review_id": 1,
               "delay": -1 })
    frontend.operation(
        "reopenreview",
        data={ "review_id": 1 })
    instance.synchronize_service("maintenance", force_maintenance=True)
    assert_branch_state(archived=False)

    # Drop the review, archive the branch, and check that it became archived,
    # then reopen the review, and check that the branch was resurrected
    # automatically.
    frontend.operation(
        "dropreview",
        data={ "review_id": 1 })
    frontend.operation(
        "archivebranch",
        data={ "review_id": 1 })
    assert_branch_state(archived=True)
    frontend.operation(
        "reopenreview",
        data={ "review_id": 1 })
    assert_branch_state(archived=False)
