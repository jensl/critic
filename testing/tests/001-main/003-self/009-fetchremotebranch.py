import os

TESTNAME = "009-fetchremotebranch"
FILENAME = "%s.txt" % TESTNAME

with repository.workcopy() as work:
    upstream_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    work.run(["branch", "%s/upstream" % TESTNAME])
    work.run(["checkout", "-b", "%s/branch" % TESTNAME])

    with open(os.path.join(work.path, FILENAME), "w") as text_file:
        print("This is a text file.", file=text_file)

    work.run(["add", FILENAME])
    work.run(["commit", "-m", "Add %s" % FILENAME],
             GIT_AUTHOR_NAME="Alice von Testing",
             GIT_AUTHOR_EMAIL="alice@example.org",
             GIT_COMMITTER_NAME="Alice von Testing",
             GIT_COMMITTER_EMAIL="alice@example.org")

    head_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    work.run(["push", "origin", "%s/upstream" % TESTNAME])
    work.run(["push", "origin", "%s/branch" % TESTNAME])

with frontend.signin("alice"):
    result = frontend.operation(
        "fetchremotebranch",
        data={ "repository_name": "critic",
               "remote": repository.url,
               "branch": "refs/heads/%s/branch" % TESTNAME,
               "upstream": "refs/heads/%s/upstream" % TESTNAME },
        expect={ "head_sha1": head_sha1,
                 "upstream_sha1": upstream_sha1 })

    commit_ids = result["commit_ids"]

    def check_commit_ids(value):
        if set(value) != set(commit_ids):
            return repr(sorted(value)), repr(sorted(commit_ids))

    frontend.operation(
        "fetchremotebranch",
        data={ "repository_name": "critic",
               "remote": repository.url,
               "branch": "%s/branch" % TESTNAME,
               "upstream": "refs/heads/%s/upstream" % TESTNAME },
        expect={ "head_sha1": head_sha1,
                 "upstream_sha1": upstream_sha1,
                 "commit_ids": check_commit_ids })
