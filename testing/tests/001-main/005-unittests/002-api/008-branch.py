# @dependency 001-main/002-createrepository.py

SHA1 = "66f25ae79dcc5e200b136388771b5924a1b5ae56"

with repository.workcopy() as work:
    work.run(["remote", "add", "critic",
              "alice@%s:/var/git/critic.git" % instance.hostname])

    work.run(["checkout", "-b", "008-branch", SHA1])
    work.run(["rebase", "--force-rebase", "HEAD~5"])
    work.run(["push", "critic", "008-branch"])

    sha1 = work.run(["rev-parse", "HEAD"]).strip()

    try:
        instance.unittest("api.branch", ["basic"],
                          args=["--sha1=" + sha1,
                                "--name=008-branch"])
    finally:
        work.run(["push", "critic", ":008-branch"])
