# @dependency 001-main/002-createrepository.py

import os

SHA1 = "66f25ae79dcc5e200b136388771b5924a1b5ae56"

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    work.run(["checkout", "-b", "010-branchupdate"])

    path = os.path.join(work.path, "010-branchupdate.txt")

    def here():
        return work.run(["rev-parse", "HEAD"]).strip()

    def commit(message):
        with open(path, "w") as message_file:
            message_file.write(message + "\n")
        work.run(["add", path])
        work.run(["commit", "-m" + message])
        return here()

    def reset(sha1):
        work.run(["reset", "--hard", sha1])

    commits = []
    previous_commits = []
    updates = []

    def push():
        work.run(["push", "--force", REMOTE_URL, "010-branchupdate"])

        update = []

        for sha1 in previous_commits:
            if sha1 not in commits:
                update.append("-" + sha1)

        for sha1 in commits:
            if sha1 not in previous_commits:
                update.append("+" + sha1)

        previous_commits[:] = commits[:]

        updates.append(here() + ":" + ",".join(update))

    commits.extend([
        commit("first commit"),
        commit("second commit"),
        commit("third commit")
    ])

    push()

    commits.extend([
        commit("fourth commit"),
        commit("fifth commit")
    ])

    push()

    # Reset the branch back to "second commit".
    reset(commits[1])
    del commits[2:]

    commits.extend([
        commit("THIRD commit"),
        commit("FOURTH commit")
    ])

    push()

    # Reset the branch back to an old ancestor commit.
    reset(SHA1)
    del commits[:]

    push()

    commits.extend([
        commit("New first commit"),
        commit("New second commit")
    ])

    push()

    logger.debug(repr(updates))

    instance.unittest("api.branchupdate", ["basic"],
                      args=["--branch-name=010-branchupdate",
                            "--updater-name=alice",
                            "--updates=" + ";".join(updates)])
