import os

TESTNAME = "010-linkification-custom"
FILENAME = "%s.txt" % TESTNAME

MESSAGE = """\
Add %(FILENAME)s

The rest of this commit message contains some "issue links".

At end of line: #1001
Followed by text: #1002 is fixed!
Followed by a period: #1003.
Followed by a comma: #1004, huh?
Within parentheses: (#1005)

That's all, folks!
""" % { "FILENAME": FILENAME }

with repository.workcopy() as work:
    work.run(["checkout", "-b", TESTNAME])

    with open(os.path.join(work.path, FILENAME), "w") as text_file:
        print >>text_file, "This line is not significant."

    work.run(["add", FILENAME])
    work.run(["commit", "-m", MESSAGE])
    work.run(["push", "alice@%s:/var/git/critic.git" % instance.hostname, "HEAD"])

instance.execute(
    ["sudo", "mkdir", "-p", "/etc/critic/main/customization",
     "&&",
     "sudo", "touch", "/etc/critic/main/customization/__init__.py",
     "&&",
     "sudo", "cp", "critic/testing/input/customization/linktypes.py",
     "/etc/critic/main/customization",
     "&&",
     "sudo", "chown", "-R", "critic.critic", "/etc/critic/main/customization"])

instance.restart()

def issue(number):
    return ("https://issuetracker.example.com/showIssue?id=%d" % number,
            "#%d" % number)

LINKS = { "At end of line": issue(1001),
          "Followed by text": issue(1002),
          "Followed by a period": issue(1003),
          "Followed by a comma": issue(1004),
          "Within parentheses": issue(1005) }

def check_link(label, expected_href, expected_string):
    def check(document):
        line_attrs = testing.expect.with_class("line", "commit-msg")
        for line in document.findAll("td", attrs=line_attrs):
            if not isinstance(line.contents[0], basestring):
                continue
            if not line.contents[0].startswith(label + ": "):
                continue
            if len(line.contents) < 2:
                continue
            link = line.contents[1]
            try:
                if link.name != "a":
                    continue
            except AttributeError:
                continue
            break
        else:
            testing.expect.check("line: '%s: <a ...>...</a>'" % label,
                                 "<expected content not found>")

        testing.expect.check(expected_href, link["href"])
        testing.expect.check(expected_string, link.string)

    return check

frontend.page(
    "critic/%s" % TESTNAME,
    expect=dict((label, check_link(label, href, string))
                for label, (href, string) in LINKS.items()))


