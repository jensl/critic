# @flag disabled

import os

# Create a branch
#
#   M --> B1:1 --> B1:2 --> B1:3
#
# (where M is origin/master) and push to Critic. Then create a second branch
#
#   B1:2 --> B2:1 --> B2:2 --> B2:3
#
# and push it to Critic. Critic will consider the second branch to be based on
# the first branch.
#
# Finally, "rebase" the second branch to be based on origin/master, and check
# what happens.

FILENAME = f"{test.name}.txt"

with repository.workcopy() as work:

    def current_sha1():
        return work.run(["rev-parse", "HEAD"]).strip()

    def commit(message):
        with open(os.path.join(work.path, FILENAME), "w") as fileobj:
            fileobj.write(message + "\n")

        work.run(["add", FILENAME])
        work.run(["commit", "-m" + message])

        return current_sha1()

    work.run(["checkout", "-b", f"{test.name}/1", "origin/master"])

    commits_1 = [commit("1/first"), commit("1/second"), commit("1/third")]

    work.run(["push", instance.repository_url("alice"), "HEAD"])

    work.run(["checkout", "-b", f"{test.name}/2", commits_1[1]])

    commits_2 = [commit("2/first"), commit("2/second"), commit("2/third")]

    work.run(["push", instance.repository_url("alice"), "HEAD"])


def branch_id(branch_name):
    return frontend.json(
        "branches", params={"repository": "critic", "name": branch_name}
    )["id"]


def branch_sha1s(branch_name):
    commits = frontend.json("branches/%d/commits" % branch_id(branch_name))["commits"]
    return set(commit["sha1"] for commit in commits)


testing.expect.equal(set(commits_1), branch_sha1s(f"{test.name}/1"))
testing.expect.equal(set(commits_2), branch_sha1s(f"{test.name}/2"))

with frontend.signin("alice"):
    frontend.operation(
        "rebasebranch",
        data={
            "repository": "critic",
            "branch_name": f"{test.name}/2",
            "base_branch_name": "master",
        },
    )

testing.expect.equal(set(commits_1), branch_sha1s(f"{test.name}/1"))
testing.expect.equal(set(commits_1[:2] + commits_2), branch_sha1s(f"{test.name}/2"))


def commit_sha1s(result, commit_ids):
    sha1_by_id = {
        commit["id"]: commit["sha1"] for commit in result["linked"]["commits"]
    }
    return [sha1_by_id[commit_id] for commit_id in commit_ids]


result = frontend.json(
    "branches/%d/branchupdates" % branch_id(f"{test.name}/2"),
    params={"include": "commits"},
)

testing.expect.equal(
    set(commits_2), set(commit_sha1s(result, result["branchupdates"][0]["associated"]))
)
testing.expect.equal([], result["branchupdates"][0]["disassociated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][1]["associated"])),
)
testing.expect.equal([], result["branchupdates"][1]["disassociated"])

with frontend.signin("alice"):
    frontend.operation(
        "rebasebranch",
        data={
            "repository": "critic",
            "branch_name": f"{test.name}/2",
            "base_branch_name": f"{test.name}/1",
        },
    )

result = frontend.json(
    "branches/%d/branchupdates" % branch_id(f"{test.name}/2"),
    params={"include": "commits"},
)

testing.expect.equal(
    set(commits_2), set(commit_sha1s(result, result["branchupdates"][0]["associated"]))
)
testing.expect.equal([], result["branchupdates"][0]["disassociated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][1]["associated"])),
)
testing.expect.equal([], result["branchupdates"][1]["disassociated"])
testing.expect.equal([], result["branchupdates"][2]["associated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][2]["disassociated"])),
)

with frontend.signin("alice"):
    frontend.operation(
        "rebasebranch",
        data={
            "repository": "critic",
            "branch_name": f"{test.name}/1",
            "base_branch_name": f"{test.name}/2",
        },
    )

result = frontend.json(
    "branches/%d/branchupdates" % branch_id(f"{test.name}/1"),
    params={"include": "commits"},
)

testing.expect.equal(
    set(commits_1), set(commit_sha1s(result, result["branchupdates"][0]["associated"]))
)
testing.expect.equal([], result["branchupdates"][0]["disassociated"])
testing.expect.equal([], result["branchupdates"][1]["associated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][1]["disassociated"])),
)

result = frontend.json(
    "branches/%d/branchupdates" % branch_id(f"{test.name}/2"),
    params={"include": "commits"},
)

testing.expect.equal(
    set(commits_2), set(commit_sha1s(result, result["branchupdates"][0]["associated"]))
)
testing.expect.equal([], result["branchupdates"][0]["disassociated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][1]["associated"])),
)
testing.expect.equal([], result["branchupdates"][1]["disassociated"])
testing.expect.equal([], result["branchupdates"][2]["associated"])
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][2]["disassociated"])),
)
testing.expect.equal(
    set(commits_1[:2]),
    set(commit_sha1s(result, result["branchupdates"][3]["associated"])),
)
testing.expect.equal([], result["branchupdates"][3]["disassociated"])
