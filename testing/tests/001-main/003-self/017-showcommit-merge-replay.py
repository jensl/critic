# Scenario: Alice opens the BRANCHES page, switches to the master branch in the
# Critic-inside-Critic repository and clicks on the merge commit 8ebec44a.
# Finally, even though the merge is empty she clicks the link "display conflict
# resolution changes" near the top of the page.

with frontend.signin("alice"):
    document = frontend.page(
        "showcommit",
        params={ "sha1": "8ebec44af03197c9679f08afc2b19606c839db99",
                 "conflicts": "yes" },
        expect={ "document_title": testing.expect.document_title(u"Merge pull request #30 from rchl/exception-fixes (8ebec44a)") })

    mailbox.check_empty()
