# Test summary
# ============
#
# Alice, Bob and Dave adds a bunch of filters making them reviewers of
# a directory we add a bunch of different files to.  Alice adds a filter with
# Erin as delegate.
#
# They all also set their Git emails, Alice and Bob sharing common@example.org
# and dave having two different addresses.
#
# Then we make a bunch of commits with different authors (all involved Git email
# addresses, plus nobody@example.org.)  Each commits adds one file.
#
# We then catch the "New Review" and "Updated Review" emails sent, and make sure
# those emails claim that the right set of files is assigned to be reviewed by
# the expected users.

import os
import re

REMOTE_URL = "alice@%s:/var/git/critic.git" % instance.hostname

to_recipient = testing.mailbox.ToRecipient
with_subject = testing.mailbox.WithSubject

with repository.workcopy() as workcopy:
    def commit(filename, author):
        path = os.path.join(workcopy.path, "028-gitemails", filename)
        with open(path, "w") as the_file:
            the_file.write("This is '%s' by %s.\n" % (filename, author))
        workcopy.run(["add", "028-gitemails/" + filename])
        workcopy.run(["commit", "-m", "Edited " + filename],
                     GIT_AUTHOR_NAME="Anonymous Coward",
                     GIT_AUTHOR_EMAIL=author + "@example.org",
                     GIT_COMMITTER_NAME="Anonymous Coward",
                     GIT_COMMITTER_EMAIL=author + "@example.org")
        return workcopy.run(["rev-parse", "HEAD"]).strip()

    def expect_mail(recipient, expected_files):
        mail = mailbox.pop(
            accept=[to_recipient(recipient + "@example.org"),
                    with_subject("(New|Updated) Review: Edited cat.txt")])

        assigned_files = []

        try:
            marker_index = mail.lines.index(
                "These changes were assigned to you:")
        except ValueError:
            pass
        else:
            for line in mail.lines[marker_index + 1:]:
                if not line.strip():
                    break
                filename, counts = line.strip().split(None, 1)
                if assigned_files:
                    filename = filename.replace(".../", "028-gitemails/")
                assigned_files.append((filename, counts))

        for filename, counts in assigned_files:
            if not expected_files:
                testing.expect.check("<no more assigned files>", filename)
            else:
                testing.expect.check(
                    "028-gitemails/" + expected_files.pop(0), filename)
                testing.expect.check("+1", counts)

        if expected_files:
            for filename in expected_files:
                testing.expect.check(filename, "<no more assigned files>")

    with frontend.signin("alice"):
        frontend.operation(
            "savesettings",
            data={ "settings": [{ "item": "review.createViaPush",
                                  "value": True }] })
        frontend.operation(
            "addfilter",
            data={ "filter_type": "reviewer",
                   "repository_name": "critic",
                   "path": "028-gitemails/",
                   "delegates": ["erin"] })
        frontend.operation(
            "setgitemails",
            data={ "subject_id": instance.userid("alice"),
                   "value": ["alice@example.org", "common@example.org"] })

    with frontend.signin("bob"):
        frontend.operation(
            "addfilter",
            data={ "filter_type": "reviewer",
                   "repository_name": "critic",
                   "path": "028-gitemails/",
                   "delegates": [] })
        frontend.operation(
            "setgitemails",
            data={ "subject_name": "bob",
                   "value": ["bob@example.org", "common@example.org"] })

    with frontend.signin("dave"):
        frontend.operation(
            "addfilter",
            data={ "filter_type": "reviewer",
                   "repository_name": "critic",
                   "path": "028-gitemails/",
                   "delegates": [] })
        frontend.operation(
            "setgitemails",
            data={ "subject": instance.userid("dave"),
                   "value": ["dave@example.org", "dave@example.com"] })

    workcopy.run(["checkout", "-b", "r/028-gitemails"])

    os.mkdir(os.path.join(workcopy.path, "028-gitemails"))

    commits = []
    commits.append(commit("cat.txt", "alice"))

    workcopy.run(["push", REMOTE_URL, "HEAD"])

    expect_mail("alice", [])
    expect_mail("bob", ["cat.txt"])
    expect_mail("dave", ["cat.txt"])
    expect_mail("erin", ["cat.txt"])

    commits.append(commit("dog.txt", "bob"))
    commits.append(commit("mouse.txt", "dave"))
    commits.append(commit("snake.txt", "dave"))
    commits.append(commit("bird.txt", "common"))
    commits.append(commit("fish.txt", "nobody"))

    workcopy.run(["push", REMOTE_URL, "HEAD"])

    expect_mail("alice", ["dog.txt", "fish.txt", "mouse.txt", "snake.txt"])
    expect_mail("bob", ["fish.txt", "mouse.txt", "snake.txt"])
    expect_mail("dave", ["bird.txt", "dog.txt", "fish.txt"])
    expect_mail("erin", ["bird.txt"])
