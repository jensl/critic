# @dependency 001-main/003-self/028-gitemails.py

HEAD = repository.run(["rev-parse", "HEAD"]).strip()
SHA1 = "66f25ae79dcc5e200b136388771b5924a1b5ae56"

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    work.run(["tag", "007-repository/simple-tag"])
    work.run(["push", REMOTE_URL, "007-repository/simple-tag"])

    work.run(["tag", "-mAnnotated", "007-repository/annotated-tag"])
    work.run(["push", REMOTE_URL, "007-repository/annotated-tag"])

    try:
        instance.unittest("api.repository", ["basic"],
                          args=["--head=" + HEAD,
                                "--sha1=" + SHA1,
                                "--path=" + instance.repository_path()])
    finally:
        work.run(["push", REMOTE_URL,
                  ":007-repository/simple-tag",
                  ":007-repository/annotated-tag"])
