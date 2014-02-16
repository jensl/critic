# @dependency 001-main/003-self/028-gitemails.py

HEAD = repository.run(["rev-parse", "HEAD"]).strip()
SHA1 = "66f25ae79dcc5e200b136388771b5924a1b5ae56"

with repository.workcopy() as work:
    work.run(["remote", "add", "critic",
              "alice@%s:/var/git/critic.git" % instance.hostname])

    work.run(["tag", "007-repository/simple-tag"])
    work.run(["push", "critic", "007-repository/simple-tag"])

    work.run(["tag", "-mAnnotated", "007-repository/annotated-tag"])
    work.run(["push", "critic", "007-repository/annotated-tag"])

    try:
        instance.unittest("api.repository", ["basic"],
                          args=["--head=" + HEAD,
                                "--sha1=" + SHA1])
    finally:
        work.run(["push", "critic",
                  ":007-repository/simple-tag",
                  ":007-repository/annotated-tag"])
