# Scenario: Bob is viewing a commit that doesn't contain any chunks that Critic
# detects as "moved code". Bob is not sure though, so he hits 'm', selects the
# appropriate filenames and clicks SEARCH. Critic should not crash.

COMMIT_WITH_NO_MOVES = 'cc1c1a25'

with frontend.signin("bob"):
    document = frontend.page(
        "critic/%s" % COMMIT_WITH_NO_MOVES,
        params={ "moves": "yes" },
        expect={ "message": testing.expect.message_title("No moved code found!") })

    mailbox.check_empty()
