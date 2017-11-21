import os

FILENAME = "filename with spaces.txt"

def check_filename(class_name):
    def check(document):
        cells = document.findAll("td", attrs=testing.expect.with_class(class_name))

        for cell in cells:
            anchor = cell.find("a")
            if not anchor:
                continue
            testing.expect.check(FILENAME, anchor.string)
            break
        else:
            testing.expect.check("<td class=%s><a>%s" % (class_name, FILENAME),
                                 "<expected content not found>")

    return check

with frontend.signin("alice"):
    with repository.workcopy(empty=True) as work:
        REMOTE_URL = instance.repository_url("alice")

        def commit():
            work.run(["add", FILENAME])
            work.run(["commit", "-m", FILENAME],
                     GIT_AUTHOR_NAME="Alice von Testing",
                     GIT_AUTHOR_EMAIL="alice@example.org",
                     GIT_COMMITTER_NAME="Alice von Testing",
                     GIT_COMMITTER_EMAIL="alice@example.org")
            return work.run(["rev-parse", "HEAD"]).strip()

        def push(sha1):
            work.run(["push", "-q", REMOTE_URL,
                      "%s:refs/roots/%s" % (sha1, sha1)])

        with open(os.path.join(work.path, FILENAME), "w") as text_file:
            print("Content of file " + FILENAME, file=text_file)

        sha1 = commit()
        push(sha1)

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
