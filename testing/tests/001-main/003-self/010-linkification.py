import os

TESTNAME = "010-linkification"
FILENAME = "%s.txt" % TESTNAME

LONG_SHA1_1 = "ca89553db7a2ba22fef70535a65beedf33c97216"
SHORT_SHA1_1 = LONG_SHA1_1[:8]

LONG_SHA1_2 = "132dbfb7c2ac0f4333fb483a70f1e8cce0333d11"
SHORT_SHA1_2 = LONG_SHA1_2[:8]

MESSAGE = """\
Add %(FILENAME)s

The rest of this commit message contains various things that should be
turned into links by the automatic linkification.

A plain HTTP URL: http://critic-review.org/tutorials.

A "wrapped" URL: <URL:mailto:jl@critic-review.org>.

A full SHA-1: %(LONG_SHA1_1)s.

A shortened SHA-1: %(SHORT_SHA1_1)s.

A diff (full SHA-1s): %(LONG_SHA1_2)s..%(LONG_SHA1_1)s.

A diff (shortened SHA-1s): %(SHORT_SHA1_2)s..%(SHORT_SHA1_1)s, should work too.

A review link: r/123 (it doesn't matter if the review exists or not.)

No review link: harrharr/1337

No SHA-1: g%(SHORT_SHA1_1)s

Also no SHA-1: %(SHORT_SHA1_1)sg
""" % { "FILENAME": FILENAME,
        "LONG_SHA1_1": LONG_SHA1_1,
        "SHORT_SHA1_1": SHORT_SHA1_1,
        "LONG_SHA1_2": LONG_SHA1_2,
        "SHORT_SHA1_2": SHORT_SHA1_2 }

with repository.workcopy() as work:
    work.run(["checkout", "-b", TESTNAME])

    with open(os.path.join(work.path, FILENAME), "w") as text_file:
        print("This line is not significant.", file=text_file)

    work.run(["add", FILENAME])
    work.run(["commit", "-m", MESSAGE])
    work.run(["push", instance.repository_url("alice"), "HEAD"])

LINKS = { "A plain HTTP URL": ("http://critic-review.org/tutorials",
                               "http://critic-review.org/tutorials" ),
          'A "wrapped" URL': ("mailto:jl@critic-review.org",
                              "&lt;URL:mailto:jl@critic-review.org&gt;"),
          "A full SHA-1": ("/critic/%s" % LONG_SHA1_1, LONG_SHA1_1),
          "A shortened SHA-1": ("/critic/%s" % LONG_SHA1_1, SHORT_SHA1_1),
          "A diff (full SHA-1s)": ("/critic/%s..%s" % (LONG_SHA1_2, LONG_SHA1_1),
                                   "%s..%s" % (LONG_SHA1_2, LONG_SHA1_1)),
          "A diff (shortened SHA-1s)": ("/critic/%s..%s" % (LONG_SHA1_2, LONG_SHA1_1),
                                        "%s..%s" % (SHORT_SHA1_2, SHORT_SHA1_1)),
          "A review link": ("/r/123", "r/123") }

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

def check_nonlink(text):
    def check(document):
        line_attrs = testing.expect.with_class("line", "commit-msg")
        for line in document.findAll("td", attrs=line_attrs):
            if line.string == text:
                break
        else:
            testing.expect.check("line: %r" % text,
                                 "<expected content not found>")

    return check

expect = dict((label, check_link(label, href, string))
              for label, (href, string) in LINKS.items())

expect["No review link"] = check_nonlink("No review link: harrharr/1337")
expect["No SHA-1"] = check_nonlink("No SHA-1: g%s" % SHORT_SHA1_1)
expect["Also no SHA-1"] = check_nonlink("Also no SHA-1: %sg" % SHORT_SHA1_1)

frontend.page(
    "critic/%s" % TESTNAME,
    expect=expect)
