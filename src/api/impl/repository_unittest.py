import sys

HEAD = None
SHA1 = None

def basic():
    import api

    assert HEAD is not None
    assert len(HEAD) == 40

    assert SHA1 is not None
    assert len(SHA1) == 40

    critic = api.critic.startSession()
    repository = api.repository.fetch(critic, repository_id=1)
    alice = api.user.fetch(critic, name="alice")

    assert isinstance(repository, api.repository.Repository)
    assert isinstance(repository.id, int)
    assert repository.id == 1
    assert isinstance(repository.name, str)
    assert repository.name == "critic"
    assert isinstance(repository.path, str)
    assert repository.path == "/var/git/critic.git"

    # FIXME: repository.url is currently broken.

    assert api.repository.fetch(critic, name="critic") is repository
    assert api.repository.fetch(
        critic, path="/var/git/critic.git") is repository

    all_repositories = api.repository.fetchAll(critic)
    assert len(all_repositories) == 1
    assert all_repositories[0] is repository

    highlighted_repositories = api.repository.fetchHighlighted(critic, alice)
    assert len(highlighted_repositories) == 1
    assert highlighted_repositories[0] is repository

    head = api.commit.fetch(repository, sha1=HEAD)

    assert HEAD == repository.resolveRef("HEAD")
    assert HEAD == repository.resolveRef("HEAD", expect="commit")
    assert HEAD.startswith(repository.resolveRef("HEAD", short=True))
    assert HEAD.startswith(repository.resolveRef("HEAD", short=8))
    assert len(repository.resolveRef("HEAD", short=8)) == 8
    assert head.tree == repository.resolveRef("HEAD", expect="tree")

    simple_tag = repository.resolveRef("007-repository/simple-tag")
    assert simple_tag == head.sha1

    annotated_tag = repository.resolveRef("007-repository/annotated-tag")
    assert annotated_tag != head.sha1
    annotated_tag = repository.resolveRef("007-repository/annotated-tag",
                                          expect="commit")
    assert annotated_tag == head.sha1

    commit0 = api.commit.fetch(repository, sha1=SHA1)
    commit1 = commit0.parents[0]
    commit2 = commit1.parents[0]
    commit3 = commit2.parents[0]
    commit4 = commit3.parents[0]
    commit5 = commit4.parents[0]

    commits = repository.listCommits(commit0, commit5)
    assert len(commits) == 5
    assert all(isinstance(commit, api.commit.Commit) for commit in commits)
    assert commits[0] == commit0
    assert commits[1] == commit1
    assert commits[2] == commit2
    assert commits[3] == commit3
    assert commits[4] == commit4

    commits = repository.listCommits((commit for commit in [commit0]),
                                     (commit for commit in [commit5]),
                                     args=["--merges"])
    assert len(commits) == 0

    commits = repository.listCommits(args=["--reverse",
                                           "%s..%s" % (commit5, commit0)])
    assert len(commits) == 5
    assert commits[0] == commit4
    assert commits[1] == commit3
    assert commits[2] == commit2
    assert commits[3] == commit1
    assert commits[4] == commit0

    # FIXME: repository.json is currently broken (uses .url which is broken.)

    try:
        api.repository.fetch(critic, repository_id=4711)
    except api.repository.InvalidRepositoryId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    try:
        api.repository.fetch(critic, name="wrong")
    except api.repository.InvalidRepositoryName:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    try:
        api.repository.fetch(critic, path="/var/git/wrong.git")
    except api.repository.InvalidRepositoryPath:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

if __name__ == "__main__":
    import coverage

    for arg in sys.argv[1:]:
        if arg.startswith("--sha1="):
            SHA1 = arg[len("--sha1="):]
        if arg.startswith("--head="):
            HEAD = arg[len("--head="):]

    if "basic" in sys.argv[1:]:
        coverage.call("unittest", basic)
