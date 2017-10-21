import datetime

# This is the commit that added the testing framework:
COMMIT_SHA1 = "78d7849db854f3544d7291cce96a0a4fa6d6843d"

# This is its tree object:
COMMIT_TREE = "c102e63ed1d612e48d3372c223559192fcf500ce"

# This is its commit message:
COMMIT_MESSAGE = """\
High-level testing framework

Framework for automated installation and "black-box" testing of Critic
running in a VirtualBox instance.
"""

# This is its "summary":
COMMIT_SUMMARY = "High-level testing framework"

# This is the SHA-1 of its parent:
COMMIT_PARENT_SHA1 = "cf0ecdeafb682bd03fba9a5bbc94e125101a5a0f"

# This is its author name, email address and timestamp:
COMMIT_AUTHOR_NAME = "Jens Lindstrom"
COMMIT_AUTHOR_EMAIL = "jl@opera.com"
COMMIT_AUTHOR_TS = datetime.datetime.fromtimestamp(1364402400)

# This is its committer name, email address and timestamp:
COMMIT_COMMITTER_NAME = "Jens Lindstrom"
COMMIT_COMMITTER_EMAIL = "jl@opera.com"
COMMIT_COMMITTER_TS = datetime.datetime.fromtimestamp(1365369848)

def basic():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    try:
        api.commit.fetch(critic, sha1=COMMIT_SHA1)
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.commit.fetch(repository)
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.commit.fetch(repository, sha1=COMMIT_SHA1, ref="something")
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.commit.fetch(repository, commit_id=0, ref="something")
    except AssertionError:
        pass
    else:
        assert False

    commit = api.commit.fetch(repository, sha1=COMMIT_SHA1)

    assert str(commit) == COMMIT_SHA1
    assert repr(commit) == "api.commit.Commit(sha1=%r)" % COMMIT_SHA1
    assert hash(commit) == hash(COMMIT_SHA1)
    assert commit == COMMIT_SHA1
    assert COMMIT_SHA1 == commit

    assert isinstance(commit.id, int), type(commit.id)
    assert isinstance(commit.sha1, str), type(commit.sha1)
    assert commit.sha1 == COMMIT_SHA1, commit.sha1
    assert isinstance(commit.tree, str), type(commit.tree)
    assert commit.tree == COMMIT_TREE, commit.tree

    assert isinstance(commit.summary, str), type(commit.summary)
    assert commit.summary == COMMIT_SUMMARY, commit.summary
    assert isinstance(commit.message, str), type(commit.message)
    assert commit.message == COMMIT_MESSAGE, commit.message

    assert isinstance(commit.parents, list), type(commit.parents)
    assert len(commit.parents) == 1, len(commit.parents)
    assert isinstance(commit.parents[0], api.commit.Commit), \
        type(commit.parents[0])
    assert commit.parents[0].sha1 == COMMIT_PARENT_SHA1, commit.parents[0].sha1

    assert isinstance(commit.description, str), type(commit.description)
    assert commit.description == "master", commit.description

    assert isinstance(commit.author, api.commit.Commit.UserAndTimestamp), \
        type(commit.author)
    assert isinstance(commit.author.name, str), type(commit.author.name)
    assert commit.author.name == COMMIT_AUTHOR_NAME, commit.author.name
    assert isinstance(commit.author.email, str), type(commit.author.email)
    assert commit.author.email == COMMIT_AUTHOR_EMAIL, commit.author.email
    assert isinstance(commit.author.timestamp, datetime.datetime), \
        type(commit.author.timestamp)
    assert commit.author.timestamp == COMMIT_AUTHOR_TS, commit.author.timestamp

    assert isinstance(commit.committer, api.commit.Commit.UserAndTimestamp), \
        type(commit.committer)
    assert isinstance(commit.committer.name, str), \
        type(commit.committer.name)
    assert commit.committer.name == COMMIT_COMMITTER_NAME, \
        commit.committer.name
    assert isinstance(commit.committer.email, str), type(commit.committer.email)
    assert commit.committer.email == COMMIT_COMMITTER_EMAIL, \
        commit.committer.email
    assert isinstance(commit.committer.timestamp, datetime.datetime), \
        type(commit.committer.timestamp)
    assert commit.committer.timestamp == COMMIT_COMMITTER_TS, \
        commit.committer.timestamp

    try:
        api.commit.fetch(repository, commit_id=47114711)
    except api.commit.InvalidCommitId:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    try:
        api.commit.fetch(repository, sha1="".join(reversed(COMMIT_SHA1)))
    except api.commit.InvalidSHA1:
        pass
    except Exception as error:
        assert False, "wrong exception raised: %s" % error
    else:
        assert False, "no exception raised"

    print("basic: ok")
