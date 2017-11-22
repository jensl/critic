# @dependency 004-repositories/003-small.py
# @users alice, bob, dave

import subprocess

FILENAME = "001-review-publish.txt"


def create_branch(branch_name, messages):
    with repository.workcopy(clone="small") as work:

        def current_sha1():
            return work.run(["rev-parse", "HEAD"]).strip()

        def commit(message):
            with open(os.path.join(work.path, FILENAME), "w") as fileobj:
                fileobj.write(message + "\n")

            work.run(["add", FILENAME])
            work.run(["commit", "-m" + message])

            return current_sha1()

        work.run(["checkout", "-b", branch_name, "origin/master"])

        commits = [commit(message) for message in messages]
        url = instance.repository_url("alice", repository="small")

        work.run(["push", "-u", url, "HEAD"])

        return commits


def commit_json(sha1):
    return frontend.json(
        "commits",
        params={"repository": "small", "sha1": sha1},
        expect=partial_json({"id": int, "sha1": sha1, "*": "*"}),
    )


def commit_id(sha1):
    return commit_json(sha1)["id"]


class RemoteRefs(object):
    def __init__(self, url):
        self.__url = url
        self.__refs = self.__fetch()

    def __fetch(self):
        output = repository.run(["ls-remote", self.__url])
        return {
            ref: sha1
            for sha1, _, ref in (line.partition("\t") for line in output.splitlines())
        }

    def update(self):
        self.added = {}
        self.updated = {}
        self.deleted = {}

        refs = self.__fetch()
        for ref, sha1 in refs.items():
            if ref not in self.__refs:
                self.added[ref] = sha1
            elif self.__refs[ref] != sha1:
                self.updated[ref] = (self.__refs[ref], sha1)
        for ref, sha1 in self.__refs.items():
            if ref not in refs:
                self.deleted[ref] = sha1
        self.__refs = refs

        return bool(self.added or self.updated or self.deleted)


refs = RemoteRefs(instance.repository_url(repository="small"))

with frontend.signin("bob"):
    frontend.json(
        "repositoryfilters",
        post={"type": "reviewer", "path": FILENAME, "repository": "small"},
        expect={
            "id": int,
            "subject": instance.userid("bob"),
            "type": "reviewer",
            "path": FILENAME,
            "repository": instance.repository("small").id,
            "delegates": [],
        },
    )

commits_1 = create_branch("001-review-publish/1", ["1/first", "1/second", "1/third"])

testing.expect.true(refs.update())
testing.expect.equal({"refs/heads/001-review-publish/1": commits_1[-1]}, refs.added)
testing.expect.equal({}, refs.updated)
testing.expect.equal({}, refs.deleted)

with frontend.signin("alice"):
    review_1 = frontend.json(
        "reviews",
        post={"repository": "small", "commits": commits_1, "owners": ["alice", "dave"]},
        expect=partial_json(
            {
                "id": int,
                "state": "draft",
                "summary": None,
                "owners": [instance.userid("alice"), instance.userid("dave")],
                "assigned_reviewers": [],
                "repository": instance.repository("small").id,
                "branch": None,
                "changesets": None,
                "partitions": [
                    {
                        "commits": [commit_id(sha1) for sha1 in reversed(commits_1)],
                        "rebase": None,
                    }
                ],
            }
        ),
    )

    instance.synchronize_service("reviewupdater")

    # No mails should be sent yet.
    mailbox.check_empty()

    testing.expect.true(refs.update())
    testing.expect.equal({"refs/keepalive/" + commits_1[-1]: commits_1[-1]}, refs.added)
    testing.expect.equal({}, refs.updated)
    testing.expect.equal({}, refs.deleted)

    review_1 = frontend.json(
        "reviews/%d" % review_1["id"],
        expect=partial_json(
            {
                "id": int,
                "state": "draft",
                "summary": None,
                "owners": [instance.userid("alice"), instance.userid("dave")],
                "assigned_reviewers": [instance.userid("bob")],
                "repository": instance.repository("small").id,
                "branch": None,
                "changesets": list,
                "partitions": [
                    {
                        "commits": [commit_id(sha1) for sha1 in reversed(commits_1)],
                        "rebase": None,
                    }
                ],
            }
        ),
    )

    frontend.json(
        "reviews/%d" % review_1["id"],
        put={"state": "open"},
        expected_http_status=400,
        expect=partial_json({"error": {"message": "Review summary not set"}}),
    )

    review_1 = frontend.json(
        "reviews/%d" % review_1["id"],
        put={"summary": "001-review-publish #1"},
        expect=partial_json(
            {"id": review_1["id"], "summary": "001-review-publish #1", "branch": None}
        ),
    )

    testing.expect.false(refs.update())

    frontend.json(
        "reviews/%d" % review_1["id"],
        put={"state": "open"},
        expected_http_status=400,
        expect=partial_json({"error": {"message": "Review branch not set"}}),
    )

    review_1 = frontend.json(
        "reviews/%d" % review_1["id"],
        params={"include": "branches"},
        put={"branch": "r/001-review-publish/1"},
        expect=partial_json(
            {
                "id": review_1["id"],
                "summary": "001-review-publish #1",
                "branch": int,
                "assigned_reviewers": [instance.userid("bob")],
                "linked": {
                    "branches": [
                        {
                            "id": int,
                            "repository": instance.repository("small").id,
                            "name": "r/001-review-publish/1",
                            "head": commit_id(commits_1[-1]),
                        }
                    ]
                },
            }
        ),
    )
    branch_1 = review_1["linked"]["branches"][0]

    testing.expect.true(refs.update())
    testing.expect.equal(
        {"refs/heads/r/001-review-publish/1": commits_1[-1]}, refs.added
    )
    testing.expect.equal({}, refs.updated)
    testing.expect.equal({}, refs.deleted)

    frontend.json(
        "branches/%d/commits" % branch_1["id"],
        expect={"commits": [commit_json(sha1) for sha1 in reversed(commits_1)]},
    )

    instance.synchronize_service("reviewupdater")

    review_1 = frontend.json(
        "reviews/%d" % review_1["id"],
        put={"state": "open"},
        expect=partial_json({"id": review_1["id"], "state": "open"}),
    )

expected_mail = NewReviewMail(review_1["id"])

to_alice = mail_to("alice", expected_mail)
to_bob = mail_to("bob", expected_mail)
to_dave = mail_to("dave", expected_mail)

# No other mails should be sent.
mailbox.check_empty()

commits_2 = create_branch("r/001-review-publish/2", ["2/first", "2/second", "2/third"])

review_2 = frontend.json(
    "reviews",
    params={"repository": "small", "branch": "r/001-review-publish/2"},
    expect=partial_json(
        {
            "id": int,
            "state": "draft",
            "summary": None,
            "owners": [instance.userid("alice")],
            "assigned_reviewers": [instance.userid("bob")],
            "repository": instance.repository("small").id,
            "branch": int,
            "partitions": [
                {
                    "commits": [commit_id(sha1) for sha1 in reversed(commits_2)],
                    "rebase": None,
                }
            ],
        }
    ),
)

with frontend.signin("alice"):
    review_2 = frontend.json(
        "reviews/%d" % review_2["id"],
        put={"state": "open", "summary": "001-review-publish #2"},
        expect=partial_json(
            {"id": review_2["id"], "state": "open", "summary": "001-review-publish #2"}
        ),
    )

to_alice = mail_to("alice", NewReviewMail(review_2["id"]))
to_bob = mail_to("bob", NewReviewMail(review_2["id"]))

# No other mails should be sent.
mailbox.check_empty()
