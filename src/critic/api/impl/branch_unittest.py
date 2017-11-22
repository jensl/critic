# mypy: ignore-errors


def basic(arguments):
    from critic import api

    assert arguments.sha1 is not None, "missing argument: --sha1"
    assert arguments.name is not None, "missing argument: --name"

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, repository_id=1)
    branch = api.branch.fetch(critic, repository=repository, name=arguments.name)

    assert isinstance(branch, api.branch.Branch)
    assert isinstance(branch.id, int)
    assert isinstance(branch.name, str)
    assert branch.name == arguments.name
    assert branch.repository is repository
    assert isinstance(branch.head, api.commit.Commit)
    assert branch.head.sha1 == arguments.sha1
    assert isinstance(branch.commits, api.commitset.CommitSet)
    assert len(branch.commits) == 5
    assert len(branch.commits.heads) == 1
    assert branch.head in branch.commits.heads

    assert api.branch.fetch(critic, branch_id=branch.id) is branch

    branches = api.branch.fetchAll(critic)
    assert isinstance(branches, list)
    assert all(isinstance(branch, api.branch.Branch) for branch in branches)
    assert branch in branches

    branches = api.branch.fetchAll(critic, repository=repository)
    assert isinstance(branches, list)
    assert all(isinstance(branch, api.branch.Branch) for branch in branches)
    assert branch in branches

    try:
        api.branch.fetch(critic, branch_id=4711)
    except api.branch.InvalidId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    try:
        api.branch.fetch(critic, repository=repository, name=arguments.name + "-wrong")
    except api.branch.InvalidName:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    print("basic: ok")


def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--sha1")
    parser.add_argument("--name")
    parser.add_argument("tests", nargs=argparse.REMAINDER)

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "basic":
            basic(arguments)
