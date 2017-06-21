# @dependency 001-main/002-createrepository.py

import os

BRANCH = "006-branchupdates"
FILENAME = "006-branchupdates.txt"

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    def commit(message):
        with open(os.path.join(work.path, FILENAME), "a") as fileobj:
            fileobj.write(message + "\n")
        work.run(["add", FILENAME])
        work.run(["commit", "-m" + message])
        return work.run(["rev-parse", "HEAD"]).strip()

    def push(*args):
        work.run(["push"] +
                 list(args) +
                 [REMOTE_URL, "HEAD:refs/heads/" + BRANCH])

    def commit_id(sha1):
        commit = frontend.json(
            "repositories/1/commits",
            params={ "sha1": sha1 })
        return commit["id"]

    commits = [
        commit("first"),
        commit("second"),
        commit("third")
    ]

    push()

    branch = frontend.json(
        "repositories/1/branches",
        params={ "name": "006-branchupdates" })

    branchupdates = [
        {
            "id": int,
            "branch": branch["id"],
            "updater": instance.userid("alice"),
            "from_head": None,
            "to_head": commit_id(commits[-1]),
            "associated": [commit_id(sha1) for sha1 in reversed(commits)],
            "disassociated": [],
            "timestamp": float,
            "output": str,
        },
    ]

    frontend.json(
        "branches/%d/branchupdates" % branch["id"],
        expect={
            "branchupdates": branchupdates,
        })

    associated_commits = [
        commit("fourth"),
        commit("fifth")
    ]
    commits.extend(associated_commits)

    push()

    branchupdates.append({
        "id": int,
        "branch": branch["id"],
        "updater": instance.userid("alice"),
        "from_head": branchupdates[-1]["to_head"],
        "to_head": commit_id(commits[-1]),
        "associated": [commit_id(sha1)
                       for sha1 in reversed(associated_commits)],
        "disassociated": [],
        "timestamp": float,
        "output": "Associated 2 new commits to the branch.",
    })

    frontend.json(
        "branches/%d/branchupdates" % branch["id"],
        expect={
            "branchupdates": branchupdates,
        })

    work.run(["reset", "--hard", "HEAD^"])

    disassociated_commits = [commits[-1]]
    del commits[-1]

    associated_commits = [
        commit("fifth^")
    ]
    commits.extend(associated_commits)

    push("-f")

    branchupdates.append({
        "id": int,
        "branch": branch["id"],
        "updater": instance.userid("alice"),
        "from_head": branchupdates[-1]["to_head"],
        "to_head": commit_id(commits[-1]),
        "associated": [commit_id(sha1)
                       for sha1 in reversed(associated_commits)],
        "disassociated": [commit_id(sha1)
                          for sha1 in reversed(disassociated_commits)],
        "timestamp": float,
        "output": ("Associated 1 new commit to the branch.\n"
                   "Disassociated 1 old commit from the branch."),
    })

    frontend.json(
        "branches/%d/branchupdates" % branch["id"],
        expect={
            "branchupdates": branchupdates,
        })
