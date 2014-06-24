# Scenario: Alice creates a review of a single commit with review filters that
# make Bob a reviewer and Dave a watcher, and then pushes a second commit to
# that review.
#
# Checks: Mostly that this doesn't fail completely, and that the expected mails
# appear to be sent.

import re

# Random commit on master:
COMMIT_SHA1 = "f771149aba230c4712c9cb9c6af4ccfea2b7967d"
COMMIT_SUMMARY = "Minor /dashboard query optimizations"

# The next commit on master:
FOLLOWUP_SHA1 = "e0892183f38932cec0d33408bdfebb290a13f8f3"

def check_summary_input(document):
    input = document.find("input", attrs={ "id": "summary" })

    if not input:
        testing.expect.check("<review summary input>",
                             "<expected content not found>")

    testing.expect.check(COMMIT_SUMMARY, input["value"])

with frontend.signin("alice"):
    # Loading /createreview first is not really necessary, but might as well try
    # that as well.

    document = frontend.page(
        "createreview",
        expect={ "document_title": testing.expect.document_title(u"Create Review") })

    document = frontend.page(
        "createreview",
        params={ "repository": "critic",
                 "commits": COMMIT_SHA1 },
        expect={ "document_title": testing.expect.document_title(u"Create Review"),
                 "summary_input": check_summary_input })

    scripts = document.findAll("script")

    for script in scripts:
        if script.has_key("src"):
            continue
        match = re.search(
            r"^\s*var review_data\s*=\s*\{\s*commit_ids:\s*\[\s*(\d+)\s*\]",
            script.string, re.MULTILINE)
        if match:
            commit_id = int(match.group(1))
            break
    else:
        testing.expect.check("<data script>",
                             "<expected content not found>")

    result = frontend.operation(
        "submitreview",
        data={ "repository_id": 1,
               "commit_ids": [commit_id],
               "branch": "r/004-createreview",
               "summary": COMMIT_SUMMARY,
               "applyfilters": True,
               "applyparentfilters": True,
               "reviewfilters": [{ "username": "bob",
                                   "type": "reviewer",
                                   "path": "/" },
                                 { "username": "dave",
                                   "type": "watcher",
                                   "path": "/" }],
               "recipientfilters": { "mode": "opt-out" }},
        expect={ "review_id": 1 })

    def to(name):
        return testing.mailbox.ToRecipient("%s@example.org" % name)

    def check_initial(mail):
        testing.expect.check("New Review: %s" % COMMIT_SUMMARY,
                             mail.header("Subject"))
        line = "Commit: %s" % COMMIT_SHA1
        if line not in to_alice.lines:
            testing.expect.check("<%r line>" % line,
                                 "<expected content not found>")

    to_alice = mailbox.pop(accept=to("alice"))
    check_initial(to_alice)
    testing.expect.check("owner",
                         to_alice.header("OperaCritic-Association"))

    to_bob = mailbox.pop(accept=to("bob"))
    check_initial(to_bob)
    testing.expect.check("reviewer",
                         to_bob.header("OperaCritic-Association"))

    to_dave = mailbox.pop(accept=to("dave"))
    check_initial(to_dave)
    testing.expect.check("watcher",
                         to_dave.header("OperaCritic-Association"))

    mailbox.check_empty()

    with repository.workcopy() as work:
        work.run(["checkout", "-q", "-b", "r/004-createreview", COMMIT_SHA1])
        work.run(["cherry-pick", FOLLOWUP_SHA1])

        followup_sha1 = work.run(["rev-parse", "HEAD"]).strip()

        work.run([
            "push", "-q", "alice@%s:/var/git/critic.git" % instance.hostname,
            "HEAD:refs/heads/r/004-createreview"])

    def check_followup(mail):
        testing.expect.check("Updated Review: %s" % COMMIT_SUMMARY,
                             mail.header("Subject"))
        line = "Commit: %s" % followup_sha1
        if line not in mail.lines:
            testing.expect.check("<%r line>" % line,
                                 "<expected content not found>")

    to_alice = mailbox.pop(accept=to("alice"))
    check_followup(to_alice)

    to_bob = mailbox.pop(accept=to("bob"))
    check_followup(to_bob)

    to_dave = mailbox.pop(accept=to("dave"))
    check_followup(to_dave)

    mailbox.check_empty()
