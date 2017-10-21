def basic():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    def fetch_review(number):
        branch = api.branch.fetch(critic, repository=repository,
                                  name="r/020-reviewrebase/%d" % number)
        return api.review.fetch(critic, branch=branch)

    def check_partition(partition):
        assert isinstance(partition, api.log.partition.Partition)

    def check_commits(commits, summaries):
        assert isinstance(commits, api.commitset.CommitSet)
        assert len(commits) == len(summaries)
        for commit, summary in zip(commits.topo_ordered, summaries):
            assert commit.summary == summary

    def check_following(partition, rebase_class):
        edge = partition.following
        assert isinstance(edge, api.log.partition.Partition.Edge)
        assert isinstance(edge.rebase, rebase_class)
        assert isinstance(edge.partition, api.log.partition.Partition)
        assert edge.partition is not partition
        mirror = edge.partition.preceding
        assert mirror.partition is partition
        assert mirror.rebase is edge.rebase
        return edge.partition

    #
    # 020-reviewrebase, test 1
    #

    partition = fetch_review(1).first_partition
    assert partition.preceding is None
    check_partition(partition)
    check_commits(partition.commits, ["Test #1, commit 6",
                                      "Test #1, commit 5",
                                      "Test #1, commit 4"])
    partition = check_following(partition, api.log.rebase.HistoryRewrite)
    check_partition(partition)
    check_commits(partition.commits, ["Test #1, commit 3",
                                      "Test #1, commit 2",
                                      "Test #1, commit 1"])
    assert partition.following is None

    #
    # 020-reviewrebase, test 2
    #

    partition = fetch_review(2).first_partition

    assert partition.preceding is None
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.HistoryRewrite)
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, ["Test #2, commit 3",
                                      "Test #2, commit 2",
                                      "Test #2, commit 1"])
    assert partition.following is None

    #
    # 020-reviewrebase, test 3
    #

    partition = fetch_review(3).first_partition
    assert partition.preceding is None
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.HistoryRewrite)
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, ["Test #3, commit 3",
                                      "Test #3, commit 2",
                                      "Test #3, commit 1"])
    assert partition.following is None

    #
    # 020-reviewrebase, test 4
    #

    partition = fetch_review(4).first_partition
    assert partition.preceding is None
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, [("Merge branch '020-reviewrebase-4-1' "
                                       "into 020-reviewrebase-4-2"),
                                      "Test #4, commit 3",
                                      "Test #4, commit 2",
                                      "Test #4, commit 1"])
    assert partition.following is None

    #
    # 020-reviewrebase, test 5
    #

    partition = fetch_review(5).first_partition
    assert partition.preceding is None
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.MoveRebase)
    check_partition(partition)
    check_commits(partition.commits, [])
    partition = check_following(partition, api.log.rebase.HistoryRewrite)
    check_partition(partition)
    check_commits(partition.commits, ["Test #5, commit 3",
                                      "Test #5, commit 2",
                                      "Test #5, commit 1"])
    assert partition.following is None

    print("basic: ok")
