# Scenario: Alice creates a review of a single commit with a review filter with
# empty path.  Loading the review front-page after that should not crash, but
# did due to a problem introduced by the filter system rewrite.

import re

# Random commit on master:
COMMIT_SHA1 = "f771149aba230c4712c9cb9c6af4ccfea2b7967d"
REVIEW_SUMMARY = "006-showreview-reviewfilter.py"

with frontend.signin("alice"):
    # Loading /createreview is not really necessary, but might as well try that
    # as well.
    document = frontend.page(
        "createreview",
        params={ "repository": "critic",
                 "commits": COMMIT_SHA1 })

    scripts = document.findAll("script")

    for script in scripts:
        if "src" in script:
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
        data={ "repository": 1,
               "commit_ids": [commit_id],
               "branch": "r/006-showreview-reviewfilter",
               "summary": REVIEW_SUMMARY,
               "applyfilters": True,
               "applyparentfilters": True,
               "reviewfilters": [{ "username": "bob",
                                   "type": "reviewer",
                                   "path": "" },
                                 { "username": "dave",
                                   "type": "watcher",
                                   "path": "" },
                                 { "username": "erin",
                                   "type": "watcher",
                                   "path": "" } ],
               "recipientfilters": { "mode": "opt-out",
                                     "excluded": ["erin"] }})

    instance.synchronize_service("reviewupdater")

    def to(name):
        return testing.mailbox.ToRecipient("%s@example.org" % name)

    mailbox.pop(accept=to("alice"))
    mailbox.pop(accept=to("bob"))
    mailbox.pop(accept=to("dave"))

    mailbox.check_empty()

    review_id = result["review_id"]
    document_title = "r/%d (No progress) - %s - Opera Critic" % (review_id, REVIEW_SUMMARY)

with frontend.signin("admin"):
    frontend.page(
        "r/%d" % review_id,
        expect={ "document_title": testing.expect.document_title(document_title) })
