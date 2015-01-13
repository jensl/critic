def basic():
    import api

    critic = api.critic.startSession()
    repository = api.repository.fetch(critic, name="critic")
    alice = api.user.fetch(critic, name="alice")

    def fetch_review(number=None):
        if number is None:
            name = "r/012-replayrebase"
        else:
            name = "r/020-reviewrebase/%d" % number
        branch = api.branch.fetch(critic, repository=repository, name=name)
        return api.review.fetch(critic, branch=branch)

    def check_history_rewrite(rebase, old_head_summary, new_head_summary):
        assert isinstance(rebase, api.log.rebase.HistoryRewrite)
        assert api.log.rebase.fetch(critic, rebase_id=rebase.id) is rebase
        assert rebase.old_head.summary == old_head_summary, (rebase.old_head.summary, old_head_summary)
        assert rebase.new_head.summary == new_head_summary, (rebase.new_head.summary, new_head_summary)

    def check_move_rebase(rebase, old_head_summary, new_head_summary,
                          old_upstream_summary, new_upstream_summary,
                          expect=None):
        assert isinstance(rebase, api.log.rebase.MoveRebase)
        assert api.log.rebase.fetch(critic, rebase_id=rebase.id) is rebase
        assert all(isinstance(commit, api.commit.Commit)
                   for commit in (rebase.old_head, rebase.new_head,
                                  rebase.old_upstream, rebase.new_upstream))
        assert rebase.old_head.summary == old_head_summary, (rebase.old_head.summary, old_head_summary)
        assert rebase.new_head.summary == new_head_summary, (rebase.new_head.summary, new_head_summary)
        if old_upstream_summary is not None:
            assert rebase.old_upstream.summary == old_upstream_summary
        if new_upstream_summary is not None:
            assert rebase.new_upstream.summary == new_upstream_summary
        if expect == "equivalent_merge":
            assert isinstance(rebase.equivalent_merge, api.commit.Commit)
        else:
            assert rebase.equivalent_merge is None
        if expect == "replayed_rebase":
            assert isinstance(rebase.replayed_rebase, api.commit.Commit)
        else:
            assert rebase.replayed_rebase is None
        assert rebase.creator is alice

    #
    # 012-replayrebase
    #

    rebases = fetch_review().rebases

    assert len(rebases) == 1
    check_move_rebase(rebases[0],
                      old_head_summary="Use temporary clones for relaying instead of temporary remotes",
                      new_head_summary="Use temporary clones for relaying instead of temporary remotes",
                      old_upstream_summary="Add test for diffs including the initial commit",
                      new_upstream_summary="Add utility function for creating a user",
                      expect="replayed_rebase")

    #
    # 020-reviewrebase, test 1
    #

    rebases = fetch_review(1).rebases

    assert len(rebases) == 1
    check_history_rewrite(rebases[0],
                          old_head_summary="Test #1, commit 3",
                          new_head_summary="Test #1, commit 1")

    #
    # 020-reviewrebase, test 2
    #

    rebases = fetch_review(2).rebases

    assert len(rebases) == 3
    check_move_rebase(rebases[0],
                      old_head_summary="Test #2, commit 7",
                      new_head_summary="Test #2, commit 8",
                      old_upstream_summary="Test #2 base, commit 2",
                      new_upstream_summary="Test #2 base, commit 1",
                      expect="replayed_rebase")
    check_history_rewrite(rebases[1],
                          old_head_summary="Test #2, commit 6",
                          new_head_summary="Test #2, commit 7")
    check_move_rebase(rebases[2],
                      old_head_summary="Test #2, commit 3",
                      new_head_summary="Test #2, commit 6",
                      old_upstream_summary="Test #2 base, commit 1",
                      new_upstream_summary="Test #2 base, commit 2",
                      expect="equivalent_merge")

    #
    # 020-reviewrebase, test 3
    #

    rebases = fetch_review(3).rebases

    assert len(rebases) == 3
    check_move_rebase(rebases[0],
                      old_head_summary="Test #3, commit 7",
                      new_head_summary="Test #3, commit 8",
                      old_upstream_summary="Test #3 base, commit 2",
                      new_upstream_summary="Test #3 base, commit 1",
                      expect="replayed_rebase")
    check_history_rewrite(rebases[1],
                          old_head_summary="Test #3, commit 6",
                          new_head_summary="Test #3, commit 7")
    check_move_rebase(rebases[2],
                      old_head_summary="Test #3, commit 3",
                      new_head_summary="Test #3, commit 6",
                      old_upstream_summary="Test #3 base, commit 1",
                      new_upstream_summary="Test #3 base, commit 2",
                      expect="equivalent_merge")

    #
    # 020-reviewrebase, test 4
    #

    rebases = fetch_review(4).rebases

    assert len(rebases) == 1
    check_move_rebase(rebases[0],
                      old_head_summary=("Merge branch '020-reviewrebase-4-1' "
                                        "into 020-reviewrebase-4-2"),
                      new_head_summary="Test #4, commit 6",
                      old_upstream_summary=None,
                      new_upstream_summary=None,
                      expect="equivalent_merge")

    #
    # 020-reviewrebase, test 5
    #

    rebases = fetch_review(5).rebases

    assert len(rebases) == 2
    check_move_rebase(rebases[0],
                      old_head_summary="Test #5, commit 1",
                      new_head_summary="Test #5, commit 4",
                      old_upstream_summary="Test #5 base, commit 2",
                      new_upstream_summary="Test #5 base, commit 1",
                      expect="replayed_rebase")
    check_history_rewrite(rebases[1],
                          old_head_summary="Test #5, commit 3",
                          new_head_summary="Test #5, commit 1")

    try:
        api.log.rebase.fetch(critic, rebase_id=10000)
    except api.log.rebase.InvalidRebaseId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    print "basic: ok"
