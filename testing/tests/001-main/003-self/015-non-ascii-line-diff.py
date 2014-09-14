import os
import json

import BeautifulSoup

TESTNAME = "015-non-ascii-line-diff"

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    def commit(encoding, content, index):
        filename = "%s.%s.txt" % (TESTNAME, encoding)

        with open(os.path.join(work.path, filename), "w") as text_file:
            text_file.write(content.encode(encoding))

        work.run(["add", filename])
        work.run(["commit", "-m", "%s (%s #%d)" % (TESTNAME, encoding, index)],
                 GIT_AUTHOR_NAME="Alice von Testing",
                 GIT_AUTHOR_EMAIL="alice@example.org",
                 GIT_COMMITTER_NAME="Alice von Testing",
                 GIT_COMMITTER_EMAIL="alice@example.org")

        return work.run(["rev-parse", "HEAD"]).strip()

    work.run(["checkout", "-b", TESTNAME])

    utf8_from_sha1 = commit("utf-8", u"Non-ascii: \xf6\n", 1)
    utf8_to_sha1 = commit("utf-8", u"Non-ascii: \xf7\n", 2)

    latin1_from_sha1 = commit("latin-1", u"Non-ascii: \xf6\n", 1)
    latin1_to_sha1 = commit("latin-1", u"Non-ascii: \xf7\n", 2)

    work.run(["push", REMOTE_URL, "HEAD"])

def check_line_diff(document):
    tbody_lines = document.findAll("tbody", attrs={ "class": "lines" })

    testing.expect.check(1, len(tbody_lines))
    testing.expect.check(1, len(tbody_lines[0].contents))

    comment = tbody_lines[0].contents[0]

    testing.expect.check(BeautifulSoup.Comment, comment.__class__)

    try:
        data = json.loads(comment)
    except ValueError:
        testing.expect.check("<valid JSON>", repr(str(comment)))

    testing.expect.check(5, len(data))

    file_id, sides, old_offset, new_offset, lines = data

    testing.expect.check(2, sides)
    testing.expect.check(1, old_offset)
    testing.expect.check(1, new_offset)
    testing.expect.check(1, len(lines))
    testing.expect.check(3, len(lines[0]))

    line_type, old_line, new_line = lines[0]

    # See diff/__init__.py, class Line
    MODIFIED = 3

    testing.expect.check(MODIFIED, line_type)
    testing.expect.check(u"Non-ascii: <ir>\xf6</i>", old_line)
    testing.expect.check(u"Non-ascii: <ir>\xf7</i>", new_line)

frontend.page(
    "showcommit",
    params={ "repository": "critic",
             "from": utf8_from_sha1,
             "to": utf8_to_sha1 },
    expect={ "utf8_line_diff": check_line_diff })

frontend.page(
    "showcommit",
    params={ "repository": "critic",
             "from": latin1_from_sha1,
             "to": latin1_to_sha1 },
    expect={ "latin1_line_diff": check_line_diff })
