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

    EXPECTED = {
        0: [dave, bob, erin, bob, alice],
        1: [alice, bob],
        2: [bob, erin, alice],
        3: [],
        4: [bob],
        5: []
    }

    def check_replies(comment):
        assert isinstance(comment, api.comment.Comment)
        assert isinstance(comment.replies, list)

        expected = EXPECTED[comment_id_map[comment.id]]

        assert len(comment.replies) == len(expected)

        for index, (reply, author) in enumerate(zip(comment.replies, expected)):
            assert isinstance(reply, api.reply.Reply)
            assert isinstance(reply.id, int)
            assert isinstance(reply.is_draft, bool)
            assert not reply.is_draft
            assert reply.comment is comment
            assert reply.author is author, (comment.id, index, reply.author.name)
            assert isinstance(reply.timestamp, datetime.datetime)
            assert isinstance(reply.text, str)
            assert reply.text == ("This is a reply from %s."
                                  % author.name.capitalize())

            assert api.reply.fetch(critic, reply_id=reply.id) is reply

    comments = api.comment.fetchAll(critic, review=review)
    assert isinstance(comments, list)
    assert len(comments) == 6

    comment_id_map = {
        comment.id: index
        for index, comment in enumerate(comments)
    }

    for comment in comments:
        check_replies(comment)

    reply_ids = [
        reply.id
        for reply in reversed(comments[0].replies[:3])
    ]

    some_replies = api.reply.fetchMany(critic, reply_ids)

    assert len(some_replies) == 3
    assert some_replies[0].id == reply_ids[0]
    assert some_replies[0] is api.reply.fetch(critic, reply_ids[0])
    assert some_replies[1].id == reply_ids[1]
    assert some_replies[1] is api.reply.fetch(critic, reply_ids[1])
    assert some_replies[2].id == reply_ids[2]
    assert some_replies[2] is api.reply.fetch(critic, reply_ids[2])

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
