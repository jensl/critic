# Scenario: Alice opens the BRANCHES page, switches to the master branch in the
# Critic-inside-Critic repository and clicks on the merge commit 8ebec44a.
# Finally, even though the merge is empty she clicks the link "display conflict
# resolution changes" near the top of the page. After that she also views
# 030afecd which had some actual conflicts.

document_title = testing.expect.document_title("Merge pull request #30 from rchl/exception-fixes (8ebec44a)")
with frontend.signin("alice"):
    document = frontend.page(
        "showcommit",
        params={ "sha1": "8ebec44af03197c9679f08afc2b19606c839db99",
                 "conflicts": "yes" },
        expect={ "document_title": document_title })

document_title = testing.expect.document_title("Merge remote-tracking branch 'github/master' into r/molsson/showcommit_sends_no_data (030afecd)")
frontend.page(
    url="showcommit",
    params={ "sha1": "030afecdfb40235af03faa52a2a193c7d8199b66",
             "conflicts": "yes" },
    expect={ "document_title": document_title })

mailbox.check_empty()
