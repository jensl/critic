def basic(arguments):
    import api

    assert arguments.sha1 is not None
    assert len(arguments.sha1) == 40

    assert arguments.head is not None
    assert len(arguments.head) == 40

    assert arguments.path is not None

    critic = api.critic.startSession()
    repository = api.repository.fetch(critic, repository_id=1)
    alice = api.user.fetch(critic, name="alice")

    assert isinstance(repository, api.repository.Repository)
    assert isinstance(repository.id, int)
    assert repository.id == 1
    assert isinstance(repository.name, str)
    assert repository.name == "critic"
    assert isinstance(repository.path, str)
    assert repository.path == arguments.path

    # FIXME: repository.url is currently broken.

    assert api.repository.fetch(critic, name="critic") is repository
    assert api.repository.fetch(critic, path=arguments.path) is repository

    all_repositories = api.repository.fetchAll(critic)
    assert len(all_repositories) == 1
    assert all_repositories[0] is repository

    highlighted_repositories = api.repository.fetchHighlighted(critic, alice)
    assert len(highlighted_repositories) == 1
    assert highlighted_repositories[0] is repository

    head = api.commit.fetch(repository, sha1=arguments.head)

    assert arguments.head == repository.resolveRef("HEAD")
    assert arguments.head == repository.resolveRef("HEAD", expect="commit")
    assert arguments.head.startswith(repository.resolveRef("HEAD", short=True))
    assert arguments.head.startswith(repository.resolveRef("HEAD", short=8))
    assert len(repository.resolveRef("HEAD", short=8)) == 8
    assert head.tree == repository.resolveRef("HEAD", expect="tree")

    simple_tag = repository.resolveRef("007-repository/simple-tag")
    assert simple_tag == head.sha1

    annotated_tag = repository.resolveRef("007-repository/annotated-tag")
    assert annotated_tag != head.sha1
    annotated_tag = repository.resolveRef("007-repository/annotated-tag",
                                          expect="commit")
    assert annotated_tag == head.sha1

    commit0 = api.commit.fetch(repository, sha1=arguments.sha1)
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

    print "basic: ok"

def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--sha1")
    parser.add_argument("--head")
    parser.add_argument("--path")
    parser.add_argument("tests", nargs=argparse.REMAINDER)

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "basic":
            basic(arguments)
