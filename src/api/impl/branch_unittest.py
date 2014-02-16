import sys

SHA1 = None
NAME = None

def basic():
    import api

    assert SHA1 is not None, "missing argument: --sha1"
    assert NAME is not None, "missing argument: --name"

    critic = api.critic.startSession()
    repository = api.repository.fetch(critic, repository_id=1)
    branch = api.branch.fetch(critic, repository=repository, name=NAME)

    assert isinstance(branch, api.branch.Branch)
    assert isinstance(branch.id, int)
    assert isinstance(branch.name, str)
    assert branch.name == NAME
    assert branch.repository is repository
    assert isinstance(branch.head, api.commit.Commit)
    assert branch.head.sha1 == SHA1
    assert isinstance(branch.commits, api.commitset.CommitSet)
    assert len(branch.commits) == 5
    assert len(branch.commits.heads) == 1
    assert branch.head in branch.commits.heads

    assert api.branch.fetch(critic, branch_id=branch.id) is branch

    try:
        api.branch.fetch(critic, branch_id=4711)
    except api.branch.InvalidBranchId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    try:
        api.branch.fetch(critic, repository=repository, name=NAME + "-wrong")
    except api.branch.InvalidBranchName:
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
        if arg.startswith("--name="):
            NAME = arg[len("--name="):]

    if "basic" in sys.argv[1:]:
        coverage.call("unittest", basic)
