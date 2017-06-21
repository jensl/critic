import collections
import datetime

def basic(arguments):
    import api

    Update = collections.namedtuple("Update", ["head", "removed", "added"])
    expected_updates = []

    for update in arguments.updates.split(";"):
        removed = []
        added = []
        head, _, sha1s = update.partition(":")
        for sha1 in sha1s.split(","):
            if sha1[0] == "-":
                removed.append(sha1[1:])
            else:
                added.append(sha1[1:])
        expected_updates.append(Update(head, removed, added))

    critic = api.critic.startSession(for_testing=True)
    branch = api.branch.fetch(
        critic,
        repository=api.repository.fetch(critic, name="critic"),
        name=arguments.branch_name)
    updater = api.user.fetch(
        critic,
        name=arguments.updater_name)

    updates = branch.updates

    assert len(updates) == len(expected_updates)

    branch_head = None

    for index, (update, expected_update) in enumerate(
            zip(updates, expected_updates)):
        assert isinstance(update, api.branchupdate.BranchUpdate)

        assert type(update.id) is int
        assert api.branchupdate.fetch(critic, update.id) is update

        assert update.branch is branch
        assert update.updater is updater

        assert isinstance(update.from_head, type(branch_head))
        assert isinstance(update.to_head, api.commit.Commit)
        assert isinstance(update.associated_commits, api.commitset.CommitSet)
        assert isinstance(update.disassociated_commits, api.commitset.CommitSet)
        assert isinstance(update.timestamp, datetime.datetime)
        assert isinstance(update.output, str)

        assert update.from_head is branch_head
        assert update.to_head.sha1 == expected_update.head
        assert len(update.associated_commits) == len(expected_update.added)
        assert len(update.disassociated_commits) == len(expected_update.removed)

        for update_commit, expected_sha1 in zip(
                reversed(list(update.associated_commits.topo_ordered)),
                expected_update.added):
            assert update_commit.sha1 == expected_sha1, \
                "added: %s != %s" % (update_commit, expected_sha1)

        for update_commit, expected_sha1 in zip(
                reversed(list(update.disassociated_commits.topo_ordered)),
                expected_update.removed):
            assert update_commit.sha1 == expected_sha1, \
                "removed: %s != %s" % (update_commit, expected_sha1)

        branch_head = update.to_head

    print "basic: ok"

def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--branch-name")
    parser.add_argument("--updater-name")
    parser.add_argument("--updates")
    parser.add_argument("tests", nargs=argparse.REMAINDER)

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "basic":
            basic(arguments)
