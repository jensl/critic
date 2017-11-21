import os

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

FILENAME = "020-fixup-review-via-push.txt"
SETTINGS = { "review.createViaPush": True }

with testing.utils.settings("alice", SETTINGS), frontend.signin("alice"):
    with repository.workcopy() as work:
        REMOTE_URL = instance.repository_url("alice")

        with open(os.path.join(work.path, FILENAME), "w") as text_file:
            print("Some content.", file=text_file)

        work.run(["add", FILENAME])
        work.run(["commit", "-m", """\
fixup! Commit reference

Relevant summary
"""],
                 GIT_AUTHOR_NAME="Alice von Testing",
                 GIT_AUTHOR_EMAIL="alice@example.org",
                 GIT_COMMITTER_NAME="Alice von Testing",
                 GIT_COMMITTER_EMAIL="alice@example.org")
        work.run(["push", "-q", REMOTE_URL,
                  "HEAD:refs/heads/r/020-fixup-review-via-push"])

        mailbox.pop(accept=[to("alice"), about("New Review: Relevant summary")])
