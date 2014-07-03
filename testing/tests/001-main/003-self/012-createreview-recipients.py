# Scenario: Alice creates an opt-in review and includes "bob" as a recipient.

import re

# Random commit on master:
COMMIT_SHA1 = "f771149aba230c4712c9cb9c6af4ccfea2b7967d"
COMMIT_SUMMARY = "Minor /dashboard query optimizations"

with frontend.signin("alice"):
    # Load /createreview to get commit_id.
    document = frontend.page(
        "createreview",
        params={ "repository": "critic", "commits": COMMIT_SHA1 })

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
        data={ "repository_name": "critic",
               "commit_ids": [commit_id],
               "branch": "r/012-createreview-recipients",
               "summary": COMMIT_SUMMARY,
               "applyfilters": True,
               "applyparentfilters": True,
               "reviewfilters": [{ "username": "bob",
                                   "type": "reviewer",
                                   "path": "/" },
                                 { "username": "dave",
                                   "type": "watcher",
                                   "path": "/" }],
               "recipientfilters": { "mode": "opt-in",
                                     "included": ["bob"] }})

    def to(name):
        return testing.mailbox.ToRecipient("%s@example.org" % name)

    mailbox.pop(accept=to("alice"))
    mailbox.pop(accept=to("bob"))
    mailbox.check_empty()
