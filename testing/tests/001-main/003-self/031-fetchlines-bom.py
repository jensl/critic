import os

UTF8_BOM = "\xEF\xBB\xBF"

with frontend.signin("alice"), repository.workcopy(empty=True) as work:
    REMOTE_URL = instance.repository_url("alice")

    def commit(filename):
        work.run(["add", filename])
        work.run(["commit", "-m", "Add " + filename],
                 GIT_AUTHOR_NAME="Alice von Testing",
                 GIT_AUTHOR_EMAIL="alice@example.org",
                 GIT_COMMITTER_NAME="Alice von Testing",
                 GIT_COMMITTER_EMAIL="alice@example.org")
        commit_sha1 = work.run(["rev-parse", "HEAD"]).strip()
        blob_sha1 = work.run(["ls-tree", "HEAD", filename]).strip().split()[2]
        return commit_sha1, blob_sha1

    filename_cc = "031-fetchlines.cc"
    with open(os.path.join(work.path, filename_cc), "w") as text_file:
        print >>text_file, UTF8_BOM
        print >>text_file, "\n"*42
        print >>text_file, "hello world"
    sha1, file_sha1_cc = commit(filename_cc)

    work.run(["push", "-q", REMOTE_URL,
              "%s:refs/roots/%s" % (sha1, sha1)])

    filename_py = "031-fetchlines.py"
    with open(os.path.join(work.path, filename_py), "w") as text_file:
        print >>text_file, UTF8_BOM
        print >>text_file, "\n"*42
        print >>text_file, "hello world"
    sha1, file_sha1_py = commit(filename_py)

    work.run(["push", "-q", REMOTE_URL,
              "HEAD:refs/heads/031-fetchlines"])

    frontend.operation(
        "fetchlines",
        data={ "repository_id": 1,
               "path": filename_cc,
               "sha1": file_sha1_cc,
               "ranges": [{ "offset": 1,
                            "count": 40,
                            "context": True }],
               "tabify": False })

    frontend.operation(
        "fetchlines",
        data={ "repository_id": 1,
               "path": filename_py,
               "sha1": file_sha1_py,
               "ranges": [{ "offset": 1,
                            "count": 40,
                            "context": True }],
               "tabify": False })
