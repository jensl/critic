# @dependency 004-repositories/001-critic.py
# @dependency 004-repositories/003-small.py
# @user alice

import os


def test1():
    # Create a branch
    #
    #   M:1 --> M:2 --> B1:1 --> B1:2 --> B1:3 --> B:M
    #    \                                     /
    #     \----> B2:1 ---> B2:2 ---> B2:3 ----/
    #
    # where M = origin/master and B:M is the tip of the branch, and make sure
    # that when we push it to Critic, Critic associates only B1:[1,2,3] and B:M
    # with the branch, and not B2:[1,2,3], since those commits are considered
    # part of different project, due to being branched off of master separately.

    FILENAME_1 = f"{test.name}/1.txt"
    FILENAME_2 = f"{test.name}/2.txt"

    with repository.workcopy() as work:
        work.run(["checkout", "-b", f"{test.name}/2", "origin/master^"])
        work.add(FILENAME_1=FILENAME_1, FILENAME_2=FILENAME_2)

        commits_2 = [
            work.commit("2/first", FILENAME_2="first\n"),
            work.commit("2/second", FILENAME_2="second\n"),
            work.commit("2/third", FILENAME_2="third\n"),
        ]

        work.run(["checkout", "-b", f"{test.name}/1", "origin/master"])

        commits_1 = [
            work.commit("1/first", FILENAME_1="first\n"),
            work.commit("1/second", FILENAME_1="second\n"),
            work.commit("1/third", FILENAME_1="third\n"),
        ]

        work.run(["merge", f"{test.name}/2"])

        commits_1.append(work.revparse())

        work.run(["push", instance.repository_url("alice"), "HEAD"])

    branch_id = frontend.json(
        "branches", params={"repository": "critic", "name": f"{test.name}/1"}
    )["id"]

    branch_commits = frontend.json("branches/%d/commits" % branch_id)["commits"]
    branch_sha1s = set(commit["sha1"] for commit in branch_commits)

    testing.expect.equal(set(commits_1), branch_sha1s)


def test2():
    # Perform a fast-forward update of small/master.

    with repository.workcopy(clone="small") as work:
        work.add(file=f"{test.name}/test2.txt")
        pushed_sha1s = {
            work.commit(f"{test.name}/test2 #1", file="#1\n"),
            work.commit(f"{test.name}/test2 #2", file="#2\n"),
            work.commit(f"{test.name}/test2 #3", file="#3\n"),
        }
        work.run("push", instance.repository_url("alice", repository="small"), "HEAD")

    branch_id = frontend.json(
        "branches", params={"repository": "small", "name": "master"}, extract="id"
    )

    associated, disassociated, commits = frontend.json(
        "branchupdates",
        params={"branch": branch_id, "count": 1},
        include=["commits"],
        extract=(
            "branchupdates[0].associated",
            "branchupdates[0].disassociated",
            "linked.commits",
        ),
    )

    commits = {commit["id"]: commit["sha1"] for commit in commits}
    associated_sha1s = set(commits[commit_id] for commit_id in associated)

    testing.expect.that(associated_sha1s).equals(pushed_sha1s)
    testing.expect.that(disassociated).equals([])


def test3():
    # Perform a fast-forward update of small/master, adding some commits and a
    # merge with a topic branch branched off `master^`.

    with repository.workcopy(clone="small") as work:
        work.run("checkout", "-b", f"{test.name}/test3/topic", "origin/master^")
        pushed_sha1s = {
            work.commit(f"{test.name}/test3/topic #1"),
            work.commit(f"{test.name}/test3/topic #2"),
            work.commit(f"{test.name}/test3/topic #3"),
        }
        work.run("checkout", "-")
        pushed_sha1s.update(
            {
                work.commit(f"{test.name}/test3/master #1"),
                work.commit(f"{test.name}/test3/master #2"),
                work.commit(f"{test.name}/test3/master #3"),
            }
        )
        work.run("merge", f"{test.name}/test3/topic")
        pushed_sha1s.add(work.revparse())
        work.run("push", instance.repository_url("alice", repository="small"), "HEAD")

    branch_id = frontend.json(
        "branches", params={"repository": "small", "name": "master"}, extract="id"
    )

    associated, disassociated, commits = frontend.json(
        "branchupdates",
        params={"branch": branch_id, "count": 1},
        include=["commits"],
        extract=(
            "branchupdates[0].associated",
            "branchupdates[0].disassociated",
            "linked.commits",
        ),
    )

    commits = {commit["id"]: commit["sha1"] for commit in commits}
    associated_sha1s = set(commits[commit_id] for commit_id in associated)

    testing.expect.that(associated_sha1s).equals(pushed_sha1s)
    testing.expect.that(disassociated).equals([])


def test4():
    # Perform a non-fast-forward update of small/master that removes the merge
    # commit added in the previous sub-test and adds two other commits, one of
    # which is a merge commit that merges in some of the same commits as the
    # previous merge commit.

    with repository.workcopy(clone="small") as work:
        removed_sha1s = {
            work.revparse("origin/master"),
            work.revparse("origin/master^2"),
        }
        work.run("reset", "--hard", "origin/master^1")
        pushed_sha1s = {work.commit(f"{test.name}/test4/master #1")}
        work.run("merge", "origin/master^2^")
        pushed_sha1s.add(work.revparse())
        work.run(
            "push",
            "--force",
            instance.repository_url("alice", repository="small"),
            "HEAD",
        )

    branch_id = frontend.json(
        "branches", params={"repository": "small", "name": "master"}, extract="id"
    )

    associated, disassociated, commits = frontend.json(
        "branchupdates",
        params={"branch": branch_id, "count": 1},
        include=["commits"],
        extract=(
            "branchupdates[0].associated",
            "branchupdates[0].disassociated",
            "linked.commits",
        ),
    )

    commits = {commit["id"]: commit["sha1"] for commit in commits}
    associated_sha1s = set(commits[commit_id] for commit_id in associated)
    disassociated_sha1s = set(commits[commit_id] for commit_id in disassociated)

    testing.expect.that(associated_sha1s).equals(pushed_sha1s)
    testing.expect.that(disassociated_sha1s).equals(removed_sha1s)


def test5():
    with repository.workcopy(clone="small") as work:
        work.run("checkout", "-b", f"{test.name}/test5")
        work.run("push", instance.repository_url("alice", repository="small"), "HEAD")
        work.commit("empty commit")
        work.run("push", instance.repository_url("alice", repository="small"), "HEAD")


test1()
test2()
test3()
test4()
test5()
