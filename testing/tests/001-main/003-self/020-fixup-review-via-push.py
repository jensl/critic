import os

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

FILENAME = "020-fixup-review-via-push.txt"

with frontend.signin("alice"):
    frontend.operation(
        "savesettings",
        data={ "settings": [{ "item": "review.createViaPush",
                              "value": True }] })

    with repository.workcopy() as work:
        work.run(["remote", "add", "critic",
                  "alice@%s:/var/git/critic.git" % instance.hostname])

        with open(os.path.join(work.path, FILENAME), "w") as text_file:
            print >>text_file, "Some content."

        work.run(["add", FILENAME])
        work.run(["commit", "-m", """\
fixup! Commit reference

Relevant summary
"""],
                 GIT_AUTHOR_NAME="Alice von Testing",
                 GIT_AUTHOR_EMAIL="alice@example.org",
                 GIT_COMMITTER_NAME="Alice von Testing",
                 GIT_COMMITTER_EMAIL="alice@example.org")
        work.run(["push", "-q", "critic",
                  "HEAD:refs/heads/r/020-fixup-review-via-push"])

        mailbox.pop(accept=[to("alice"), about("New Review: Relevant summary")])
