import re

def to(name):
    return testing.mailbox.to_recipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.with_subject(subject)

# The commit we'll be "reviewing."
COMMIT_SHA1 = "aca57d0899e5193232dbbea726d94a838a4274ed"
# The original parent of that commit.
PARENT_SHA1 = "ca89553db7a2ba22fef70535a65beedf33c97216"
# An ancestor of the original parent, onto which we'll be rebasing the reviewed
# commit.
TARGET_SHA1 = "132dbfb7c2ac0f4333fb483a70f1e8cce0333d11"

# The subject of the reviewed commit.
SUMMARY = "Use temporary clones for relaying instead of temporary remotes"

with frontend.signin("alice"):
    frontend.operation(
        "savesettings",
        data={ "settings": [{ "item": "review.createViaPush",
                              "value": True }] })

    with repository.workcopy() as work:
        work.run(["remote", "add", "critic",
                  "alice@%s:/var/git/critic.git" % instance.hostname])
        work.run(["checkout", "-b", "r/012-checkrebase", PARENT_SHA1])
        work.run(["cherry-pick", COMMIT_SHA1],
                 GIT_COMMITTER_NAME="Alice von Testing",
                 GIT_COMMITTER_EMAIL="alice@example.org")

        output = work.run(["push", "critic", "HEAD"])
        next_is_review_url = False

        for line in output.splitlines():
            if not line.startswith("remote:"):
                continue
            line = line[len("remote:"):].split("\x1b", 1)[0].strip()
            if line == "Submitted review:":
                next_is_review_url = True
            elif next_is_review_url:
                review_id = int(re.search(r"/r/(\d+)$", line).group(1))
                break
        else:
            testing.expect.check("<review URL in git hook output>",
                                 "<expected content not found>")

        to_alice = mailbox.pop(accept=[to("alice"),
                                       about("New Review: %s" % SUMMARY)],
                               timeout=30)
        if not to_alice:
            testing.expect.check("<mail to alice>",
                                 "<expected mail not received>")

        frontend.operation(
            "preparerebase",
            data={ "review_id": review_id,
                   "new_upstream": TARGET_SHA1 })

        work.run(["rebase", "--onto", TARGET_SHA1, PARENT_SHA1])
        work.run(["push", "--force", "critic", "HEAD"])

        to_alice = mailbox.pop(accept=[to("alice"),
                                       about("Updated Review: %s" % SUMMARY)],
                               timeout=30)
        if not to_alice:
            testing.expect.check("<mail to alice>",
                                 "<expected mail not received>")
