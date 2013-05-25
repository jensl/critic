# Random commit on master:
COMMIT_SHA1 = "bc661163b11234e85ec7b0efe1195cce473f234a"

document_title = testing.expect.document_title("Check branch review status")
content_title = testing.expect.paleyellow_title(0, "Check branch review status")

# First load /checkbranch without parameters; this just returns a form.
frontend.page(
    url="checkbranch",
    expect={ "document_title": document_title,
             "content_title": content_title })

# Create some branches.  The commits on them are not really that relevant, but
# they should not be on master.  We generate some such commits simply by
# reverting some commits that are on master.
#
# One branch is pushed to Critic's repository, but also to "origin" where it
# has one additional commit.
#
# Another branch is not pushed to Critic's repository, only to "origin".
with repository.workcopy() as work:
    work.run(["checkout", "-q", "-b", "005-checkbranch", COMMIT_SHA1])

    first_sha1 = work.run(["rev-parse", "HEAD"]).strip()
    second_sha1 = work.run(["rev-parse", "HEAD^"]).strip()
    third_sha1 = work.run(["rev-parse", "HEAD^^"]).strip()

    work.run(["revert", "--no-edit", first_sha1])
    work.run(["push", "-q", "alice@%s:/var/git/critic.git" % instance.hostname,
              "HEAD:refs/heads/005-checkbranch-1"])

    work.run(["revert", "--no-edit", second_sha1])
    work.run(["push", "-q", "origin", "HEAD:refs/heads/005-checkbranch-1"])

    work.run(["revert", "--no-edit", third_sha1])
    work.run(["push", "-q", "origin", "HEAD:refs/heads/005-checkbranch-2"])

document_title = testing.expect.document_title("Branch review status: 005-checkbranch-1")
content_title = testing.expect.paleyellow_title(0, "Unmerged Commits (1)")

# Load /checkbranch with fetch=no checking the first branch.
frontend.page(
    url="checkbranch",
    params={ "repository": "critic",
             "commit": "005-checkbranch-1",
             "upstream": "master" },
    expect={ "document_title": document_title,
             "content_title": content_title })

content_title = testing.expect.paleyellow_title(0, "Unmerged Commits (2)")

# Load /checkbranch with fetch=yes checking the first branch.
frontend.page(
    url="checkbranch",
    params={ "repository": "critic",
             "commit": "005-checkbranch-1",
             "fetch": "yes",
             "upstream": "master" },
    expect={ "document_title": document_title,
             "content_title": content_title })

message_title = testing.expect.message_title(
    "Unable to interpret '005-checkbranch-2' as a commit reference.")

# Load /checkbranch with fetch=no checking the second branch.  This essentially
# fails, since we didn't push this branch to Critic's repository.
frontend.page(
    url="checkbranch",
    params={ "repository": "critic",
             "commit": "005-checkbranch-2",
             "upstream": "master" },
    expect={ "message_title": message_title })

document_title = testing.expect.document_title("Branch review status: 005-checkbranch-2")
content_title = testing.expect.paleyellow_title(0, "Unmerged Commits (3)")

# Load /checkbranch with fetch=yes checking the second branch.
frontend.page(
    url="checkbranch",
    params={ "repository": "critic",
             "commit": "005-checkbranch-2",
             "fetch": "yes",
             "upstream": "master" },
    expect={ "document_title": document_title,
             "content_title": content_title })

content_title = testing.expect.paleyellow_title(0, "Unmerged Commits (1)")

# Load /checkbranch checking the second branch, using the first branch as the
# upstream instead of master.
frontend.page(
    url="checkbranch",
    params={ "repository": "critic",
             "commit": "005-checkbranch-2",
             "upstream": "005-checkbranch-1" },
    expect={ "document_title": document_title,
             "content_title": content_title })
