import os

# Create a branch
#
#   M1 --> M2 --> B1:1 --> B1:2 --> B1:3 --> B:M
#    \                                   /
#     \----> B2:1 --> B2:2 --> B2:3 ----/
#
# where M2 = origin/master and B:M is the tip of the branch, and make sure that
# when we push it to Critic, Critic associates only B1:[1,2,3] and B:M with the
# branch, and not B2:[1,2,3], since those commits are considered part of
# different project, due to being branched off of master separately.

FILENAME_1 = "034-branch-update/1.txt"
FILENAME_2 = "034-branch-update/2.txt"

with repository.workcopy() as work:
    def current_sha1():
        return work.run(["rev-parse", "HEAD"]).strip()

    def commit(filename, message):
        if not os.path.isdir(os.path.join(work.path, "034-branch-update")):
            os.makedirs(os.path.join(work.path, "034-branch-update"))

        with open(os.path.join(work.path, filename), "w") as fileobj:
            fileobj.write(message + "\n")

        work.run(["add", filename])
        work.run(["commit", "-m" + message])

        return current_sha1()

    work.run(["checkout", "-b", "034-branch-update/2", "origin/master^"])

    commits_2 = [commit(FILENAME_2, "2/first"),
                 commit(FILENAME_2, "2/second"),
                 commit(FILENAME_2, "2/third")]

    work.run(["checkout", "-b", "034-branch-update/1", "origin/master"])

    commits_1 = [commit(FILENAME_1, "1/first"),
                 commit(FILENAME_1, "1/second"),
                 commit(FILENAME_1, "1/third")]

    work.run(["merge", "034-branch-update/2"])

    commits_1.append(current_sha1())

    work.run(["push", instance.repository_url("alice"), "HEAD"])

branch_id = frontend.json(
    "branches",
    params={
        "repository": "critic",
        "name": "034-branch-update/1",
    })["id"]

branch_commits = frontend.json("branches/%d/commits" % branch_id)["commits"]
branch_sha1s = set(commit["sha1"] for commit in branch_commits)

testing.expect.equal(set(commits_1), branch_sha1s)
