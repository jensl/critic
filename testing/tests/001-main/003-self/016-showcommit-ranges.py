# Scenario: Alice opens the BRANCHES page, switches to the master branch in the
# Critic-inside-Critic repository and selects a range of two adjacent non-merge
# commits and verifies that there is no error. She then selects a range that
# starts with a merge commit and makes sure that the appropriate error message
# is shown.

with frontend.signin("alice"):
    # Two adjacent non-merge commits.
    document = frontend.page(
        "showcommit",
        params={ "first": "016f2149c334ff7dabac98700e74a7e9500e702e",
                 "last": "007b4b53a2a8e9561f5143eff27300ea693ca621" },
        expect={ "document_title": testing.expect.document_title("fa686f55..007b4b53"),
                 "content_title": testing.expect.paleyellow_title(0, "Squashed History") })

    # 57a886e is a merge commit.
    document = frontend.page(
        "showcommit",
        params={ "first": "57a886e6352b229991c81e7ba43244ace7e02d76",
                 "last": "b2b78ca013b49c73231bee11674bcdb3edf6d3f2" },
        expect={ "message": testing.expect.message_title("Invalid parameters; 'first' can not be a merge commit.") })

    mailbox.check_empty()
