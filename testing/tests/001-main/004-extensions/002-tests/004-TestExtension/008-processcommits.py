import os
import re

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

FILENAME = "008-processcommits.txt"
SUMMARY = "Added %s" % FILENAME
SETTINGS = { "review.createViaPush": True }

review_id = None

with testing.utils.settings("alice", SETTINGS), frontend.signin("alice"):
    with repository.workcopy() as work:
        base_sha1 = work.run(["rev-parse", "HEAD"]).strip()

        work.run(["remote", "add", "critic",
                  "alice@%s:/var/git/critic.git" % instance.hostname])

        def commit(fixup_message=None):
            if fixup_message:
                full_message = "fixup! %s\n\n%s" % (SUMMARY, fixup_message)
            else:
                full_message = SUMMARY
            work.run(["add", FILENAME])
            work.run(["commit", "-m", full_message],
                     GIT_AUTHOR_NAME="Alice von Testing",
                     GIT_AUTHOR_EMAIL="alice@example.org",
                     GIT_COMMITTER_NAME="Alice von Testing",
                     GIT_COMMITTER_EMAIL="alice@example.org")
            return work.run(["rev-parse", "HEAD"]).strip()

        def push():
            output = work.run(
                ["push", "-q", "critic",
                 "HEAD:refs/heads/r/008-processcommits"],
                TERM="dumb")
            all_lines = []
            for line in output.splitlines():
                if not line.startswith("remote:"):
                    continue
                all_lines.append(line)
            extension_lines = []
            for line in all_lines:
                line = line[len("remote:"):].strip()
                if line.startswith("[TestExtension] "):
                    extension_lines.append(line[len("[TestExtension] "):])
            return all_lines, extension_lines

        with open(os.path.join(work.path, FILENAME), "w") as text_file:
            print >>text_file, "First line."

        first_commit = commit()
        all_lines, extension_lines = push()

        for line in all_lines:
            match = testing.utils.RE_REVIEW_URL.match(line)
            if match:
                review_id = int(match.group(1))

        testing.expect.check(["processcommits.js::processcommits()",
                              "===================================",
                              "r/%d" % review_id,
                              "%s..%s" % (base_sha1[:8], first_commit[:8]),
                              "%s" % first_commit[:8]],
                             extension_lines)

        mailbox.pop(accept=[to("alice"),
                            about("New Review: %s" % SUMMARY)])

        with open(os.path.join(work.path, FILENAME), "a") as text_file:
            print >>text_file, "Second line."
        second_commit = commit("Added second line")

        with open(os.path.join(work.path, FILENAME), "a") as text_file:
            print >>text_file, "Third line."
        third_commit = commit("Added third line")

        with open(os.path.join(work.path, FILENAME), "a") as text_file:
            print >>text_file, "Fourth line."
        fourth_commit = commit("Added fourth line")

        all_lines, extension_lines = push()

        testing.expect.check(["processcommits.js::processcommits()",
                              "===================================",
                              "r/%d" % review_id,
                              "%s..%s" % (first_commit[:8], fourth_commit[:8]),
                              "%s,%s,%s" % (fourth_commit[:8],
                                            third_commit[:8],
                                            second_commit[:8])],
                             extension_lines)

        mailbox.pop(accept=[to("alice"),
                            about("Updated Review: %s" % SUMMARY)])
