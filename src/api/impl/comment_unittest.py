import sys
import datetime

def basic(arguments):
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")
    branch = api.branch.fetch(
        critic, repository=repository, name=arguments.review)
    review = api.review.fetch(critic, branch=branch)
    alice = api.user.fetch(critic, name="alice")
    bob = api.user.fetch(critic, name="bob")
    dave = api.user.fetch(critic, name="dave")
    erin = api.user.fetch(critic, name="erin")

    all_comments = api.comment.fetchAll(critic)
    assert isinstance(all_comments, list)

    EXPECTED = {
        0: { "text": "This is a general issue.",
             "location": None,
             "type": "issue",
             "state": "open" },
        1: { "text": "This is a general note.",
             "location": None,
             "type": "issue",
             "state": "open" },
        2: { "text": "This is a commit issue.",
             "location": ("commit-message", 1, 3),
             "type": "issue",
             "state": "resolved",
             "resolved_by": dave },
        3: { "text": "This is a commit note.",
             "location": ("commit-message", 5, 5),
             "type": "note" },
        4: { "text": "This is a file issue.",
             "location": ("file-version", 1, 3),
             "type": "issue",
             "state": "open" },
        5: { "text": "This is a file note.",
             "location": ("file-version", 9, 9),
             "type": "note" }
    }

    def check_comment(comment):
        assert isinstance(comment, api.comment.Comment)
        assert isinstance(comment.id, int)
        assert api.comment.fetch(critic, comment_id=comment.id) is comment

        expected = EXPECTED[comment_id_map[comment.id]]

        assert isinstance(comment.type, str)
        assert comment.type == expected["type"]
        assert isinstance(comment.is_draft, bool)
        assert not comment.is_draft
        assert comment.review is review
        assert comment.author is alice
        assert isinstance(comment.timestamp, datetime.datetime)
        assert isinstance(comment.text, str)
        assert comment.text == expected["text"]

        if comment.type == "note":
            assert isinstance(comment, api.comment.Note)
            return

        assert isinstance(comment, api.comment.Issue)
        assert isinstance(comment.state, str)
        assert comment.state == expected["state"]
        if comment.state == "resolved":
            assert comment.resolved_by is expected["resolved_by"]
        else:
            assert comment.resolved_by is None
        if comment.state == "addressed":
            assert comment.addressed_by is expected["addressed_by"]
        else:
            assert comment.addressed_by is None

        if expected["location"] is None:
            assert comment.location is None
        else:
            location_type, first_line, last_line = expected["location"]
            if location_type == "file-version":
                # FileVersionLocation is not yet supported.
                return
            assert comment.location.type == location_type
            assert comment.location.first_line == first_line
            assert comment.location.last_line == last_line, (comment.location.last_line, last_line)
            assert isinstance(comment.location, api.comment.Location)
            if location_type == "commit-message":
                assert isinstance(
                    comment.location, api.comment.CommitMessageLocation)
            else:
                assert isinstance(
                    comment.location, api.comment.FileVersionLocation)

    comments = api.comment.fetchAll(critic, review=review)
    assert isinstance(comments, list)
    assert len(comments) == 6

    comment_id_map = {
        comment.id: index
        for index, comment in enumerate(comments)
    }

    for comment in comments:
        check_comment(comment)

    some_comments = api.comment.fetchMany(critic, [3, 2, 1])

    assert len(some_comments) == 3
    assert some_comments[0].id == 3
    assert some_comments[0] is api.comment.fetch(critic, 3)
    assert some_comments[1].id == 2
    assert some_comments[1] is api.comment.fetch(critic, 2)
    assert some_comments[2].id == 1
    assert some_comments[2] is api.comment.fetch(critic, 1)

    print "basic: ok"

def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--review")
    parser.add_argument("tests", nargs=argparse.REMAINDER)

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "basic":
            basic(arguments)
