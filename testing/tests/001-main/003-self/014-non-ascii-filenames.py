# coding=utf-8

# Scenario: Alice creates a review for a commit where a file that contains
#           non-ascii chars has been added. Critic should not crash.

import os

TC_NAME_PREFIX = "014-non-ascii-filename"
TC_NAME_UTF8 = (u"%s-åäö\x01\ufffd" % TC_NAME_PREFIX).encode("utf-8")
TC_NAME_ESCAPED = u"%s-åäö\\x01\\ufffd" % TC_NAME_PREFIX

def check_filename(class_name):
    def check(document):
        cells = document.findAll("td", attrs=testing.expect.with_class(class_name))

        for cell in cells:
            anchor = cell.find("a")
            if not anchor:
                continue
            if anchor.string.startswith(TC_NAME_PREFIX):
                testing.expect.check(TC_NAME_ESCAPED, anchor.string)
                break
        else:
            testing.expect.check("<td class=%s><a>%s" % (class_name, TC_NAME_ESCAPED),
                                 "<expected content not found>")

    return check

with frontend.signin("alice"):
    with repository.workcopy(empty=True) as work:
        REMOTE_URL = instance.repository_url("alice")

        def commit():
            work.run(["add", TC_NAME_UTF8])
            work.run(["commit", "-m", TC_NAME_UTF8],
                     GIT_AUTHOR_NAME="Alice von Testing",
                     GIT_AUTHOR_EMAIL="alice@example.org",
                     GIT_COMMITTER_NAME="Alice von Testing",
                     GIT_COMMITTER_EMAIL="alice@example.org")
            return work.run(["rev-parse", "HEAD"]).strip()

        def push():
            work.run(["push", "-q", REMOTE_URL,
                      "HEAD:refs/heads/" + TC_NAME_PREFIX])

        with open(os.path.join(work.path, TC_NAME_UTF8), "w") as text_file:
            print >>text_file, "Content of file " + TC_NAME_UTF8

        sha1 = commit()
        push()

    frontend.page(
        "showcommit",
        params={ "repository": "critic",
                 "sha1": sha1 },
        expect={ "filename": check_filename("path") })

    frontend.page(
        "showtree",
        params={ "repository": "critic",
                 "sha1": sha1,
                 "path": "/" },
        expect={ "filename": check_filename("name") })
