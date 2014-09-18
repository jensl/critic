import os
import re

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

FILENAME = "008-root-commit-pending.txt"
SUMMARY = "Added %s" % FILENAME

review_id = None
commits = {}
first_commit = None
second_commit = None
third_commit = None

SETTINGS = { "review.createViaPush": True }

with testing.utils.settings("alice", SETTINGS), frontend.signin("alice"):
    with repository.workcopy(empty=True) as work:
        REMOTE_URL = instance.repository_url("alice")

        def commit(fixup_message=None):
            if fixup_message:
                full_message = "fixup! %s\n\n%s" % (SUMMARY, fixup_message)
                message = fixup_message
            else:
                full_message = message = SUMMARY
            work.run(["add", FILENAME])
            work.run(["commit", "-m", full_message],
                     GIT_AUTHOR_NAME="Alice von Testing",
                     GIT_AUTHOR_EMAIL="alice@example.org",
                     GIT_COMMITTER_NAME="Alice von Testing",
                     GIT_COMMITTER_EMAIL="alice@example.org")
            sha1 = work.run(["rev-parse", "HEAD"]).strip()
            commits[sha1] = message
            return sha1

        def push():
            work.run(["push", "-q", REMOTE_URL,
                      "HEAD:refs/heads/r/008-root-commit-pending"])

        with open(os.path.join(work.path, FILENAME), "w") as text_file:
            print >>text_file, "First line."

        first_commit = commit()

        push()

        to_alice = mailbox.pop(accept=to("alice"))
        testing.expect.check("New Review: %s" % SUMMARY,
                             to_alice.header("Subject"))

        for line in to_alice.lines:
            match = re.search(
                r"\bhttp://[^/]+/r/(\d+)\b", line)
            if match:
                review_id = int(match.group(1))
                break
        else:
            testing.expect.check("<review URL in mail>",
                                 "<expected content not found>")

        with open(os.path.join(work.path, FILENAME), "a") as text_file:
            print >>text_file, "Second line."

        second_commit = commit("Added second line")

        with open(os.path.join(work.path, FILENAME), "a") as text_file:
            print >>text_file, "Third line."

        third_commit = commit("Added third line")

        push()

        to_alice = mailbox.pop(accept=to("alice"))
        testing.expect.check("Updated Review: %s" % SUMMARY,
                             to_alice.header("Subject"))

    frontend.operation(
        "addreviewfilters",
        data={ "review_id": review_id,
               "filters": [{ "type": "reviewer",
                             "user_names": ["bob"],
                             "paths": ["/"] }] })

    mailbox.pop(accept=(to("bob"), about(r"New\(ish\) Review: %s" % SUMMARY)))
    mailbox.pop(accept=(to("bob"), about("Updated Review: %s" % SUMMARY)))

def check_squashed_history(sha1s):
    def check(document):
        table = document.find("table", attrs=testing.expect.with_class("log"))

        if not table:
            testing.expect.check("<table class='log'>",
                                 "<expected content not found>")

        links = table.findAll("a", attrs=testing.expect.with_class("commit"))

        for link in links:
            testing.expect.check(
                "%s?review=%d" % (sha1s[-1][:8], review_id), link["href"])
            del sha1s[-1]

        if sha1s:
            logger.error(
                "Commits missing from 'Squashed history':\n  %s"
                % ("\n  ".join(commits[sha1] for sha1 in sha1s)))

    return check

frontend.page("r/%d" % review_id)
frontend.page("showcommit?sha1=%s&review=%d" % (first_commit, review_id))

frontend.page(
    ("showcommit?first=%s&last=%s&review=%d"
     % (first_commit, second_commit, review_id)),
    expect={ "squashed_history": check_squashed_history([first_commit,
                                                         second_commit]) })

frontend.page(
    ("showcommit?first=%s&last=%s&review=%d"
     % (second_commit, third_commit, review_id)),
    expect={ "squashed_history": check_squashed_history([second_commit,
                                                         third_commit]) })

frontend.page(
    ("showcommit?first=%s&last=%s&review=%d"
     % (first_commit, third_commit, review_id)),
    expect={ "squashed_history": check_squashed_history([first_commit,
                                                         second_commit,
                                                         third_commit]) })

def check_path(document):
    table = document.find("table", attrs=testing.expect.with_class("filter"))

    if not table:
        testing.expect.check("<table class='filter'>",
                             "<expected content not found>")

    for cell in table.findAll("td", attrs=testing.expect.with_class("path")):
        if cell.string and cell.string == FILENAME:
            break
    else:
        testing.expect.check("<td class='path'>%s</td>" % FILENAME,
                             "<expected content not found>")

frontend.page(
    "filterchanges?review=%d" % review_id,
    expect={ "path": check_path })

frontend.page(
    ("filterchanges?first=%s&last=%s&review=%d"
     % (first_commit, second_commit, review_id)),
    expect={ "path": check_path })

frontend.page(
    ("filterchanges?first=%s&last=%s&review=%d"
     % (second_commit, third_commit, review_id)),
    expect={ "path": check_path })

frontend.page(
    ("filterchanges?first=%s&last=%s&review=%d"
     % (first_commit, third_commit, review_id)),
    expect={ "path": check_path })

with frontend.signin("bob"):
    frontend.page(
        "showcommit?review=%d&filter=pending" % review_id,
        expect={ "squashed_history": check_squashed_history([first_commit,
                                                             second_commit,
                                                             third_commit]) })

    frontend.page(
        "showcommit?review=%d&filter=reviewable" % review_id,
        expect={ "squashed_history": check_squashed_history([first_commit,
                                                             second_commit,
                                                             third_commit]) })

    frontend.page(
        "showcommit?review=%d&filter=relevant" % review_id,
        expect={ "squashed_history": check_squashed_history([first_commit,
                                                             second_commit,
                                                             third_commit]) })
