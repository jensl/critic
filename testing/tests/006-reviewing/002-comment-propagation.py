# @dependency 004-repositories/003-small.py
# @users alice, bob, dave, erin

import re
import textwrap

NONSENSE = """
Lorem ipsum dolor sit amet, consectetur adipiscing
elit. Donec ut enim sit amet purus ultricies
lobortis. Pellentesque nisi arcu, convallis sed purus sed,
semper ultrices velit. Ut egestas lorem tortor, vitae
lacinia lorem consectetur nec. Integer tempor ornare ipsum
at viverra. Curabitur nec orci mollis, lacinia sapien eget,
ultricies ipsum. Curabitur a libero tortor. Curabitur
volutpat lacinia erat, ac suscipit enim dignissim nec.
"""


def content(upper=set(), skip=set()):
    def segment(title):
        if title in upper:
            title = title.upper()
        return textwrap.indent(NONSENSE, f"[{title}] ").strip()

    def segments():
        for title in ("first", "second", "third", "fourth", "fifth"):
            if title in skip:
                continue
            yield segment(title)

    return "\n\n".join(segments())


CACHE = {}


def get_location(review, commit_sha1, segment, accept_missing):
    file_id = review.getFileId("nonsense")

    if commit_sha1 not in CACHE:
        CACHE[commit_sha1] = frontend.json(
            "filecontents",
            params={
                "repository": "small",
                "commit": commit_sha1,
                "file": file_id,
                "plain": "yes",
            },
            expect={
                "repository": instance.repository("small").id,
                "file": file_id,
                "sha1": re.compile("[0-9a-f]{40}$"),
                "lines": list,
            },
        )["lines"]

        testing.logger.debug("%s: %r", commit_sha1, CACHE[commit_sha1])

    prefix = f"[{segment}] "
    lines = set()

    for index, line in enumerate(CACHE[commit_sha1]):
        if line.startswith(prefix):
            lines.add(index + 1)
        elif lines:
            break

    if not lines:
        assert accept_missing
        return None

    return {
        "type": "file-version",
        "first_line": min(lines),
        "last_line": max(lines),
        "commit": review.getCommitId(commit_sha1),
        "file": file_id,
    }


def check_comment(comment, **expected):
    frontend.json("comments/%d" % int(comment), check=expected)


def check_locations(review, comment, segment):
    for index, commit_sha1 in enumerate(review.sha1s):
        expected_location = get_location(review, commit_sha1, segment, True)

        # actual_location = frontend.json(
        #     "comments/%d" % int(comment),
        #     commit=commit_sha1,
        #     fields="translated_location",
        #     expected_http_status=[200, 404]
        # ).get("translated_location")

        result = frontend.json(
            "comments/%d" % int(comment),
            params={"commit": commit_sha1, "fields": "translated_location"},
            expected_http_status=[200, 404],
        )
        testing.logger.debug("result=%r", result)
        actual_location = result.get("translated_location")

        testing.expect.equal(
            type(expected_location),
            type(actual_location),
            message="Commit %d (%s)" % (index, commit_sha1[:8]),
        )

        if expected_location is not None:
            for key in expected_location:
                testing.expect.equal(
                    expected_location[key],
                    actual_location.get(key),
                    message=(
                        "Commit %d (%s): same `location.%s`"
                        % (index, commit_sha1[:8], key)
                    ),
                )


def test1(work):
    review = Review(work, "alice", "037-comment-propagation")
    review.addFile(nonsense="037-comment-propagation/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit("reference", nonsense=content(skip={"first"}), reference=True)
    review.commit("commit #1", nonsense=content(upper={"second"}, skip={"first"}))
    review.commit(
        "commit #2", nonsense=content(upper={"second"}, skip={"first", "fourth"})
    )
    review.submit()

    review.addFilter("dave", "reviewer", "/")
    review.addFilter("erin", "reviewer", "/")
    review.flushFilters()

    with frontend.signin("bob"):
        issue_1 = frontend.json(
            "reviews/%d/issues" % review.id,
            post={
                "text": "Issue on second segment",
                "location": get_location(review, review.sha1s[1], "SECOND", False),
            },
            expect=partial_json({"is_draft": True}),
        )["id"]
        check_comment(issue_1, state="open")
        check_locations(review, issue_1, "SECOND")

        issue_2 = frontend.json(
            "reviews/%d/issues" % review.id,
            post={
                "text": "Issue on fifth segment",
                "location": get_location(review, review.sha1s[1], "fifth", False),
            },
            expect=partial_json({"is_draft": True}),
        )["id"]
        check_comment(issue_2, state="open")
        check_locations(review, issue_2, "fifth")

        frontend.json(
            "reviews/%d/batches" % review.id,
            params={"unpublished": "yes"},
            expect=partial_json(
                {
                    "id": None,
                    "review": review.id,
                    "author": instance.user("bob").id,
                    "comment": None,
                    "created_comments": [issue_1, issue_2],
                }
            ),
        )

        frontend.json(
            "reviews/%d/batches" % review.id,
            post={"comment": "Bob's issues"},
            expect=partial_json(
                {
                    "id": int,
                    "review": review.id,
                    "author": instance.user("bob").id,
                    "comment": int,
                    "created_comments": [issue_1, issue_2],
                }
            ),
        )

    def checkBobsIssues(mail):
        testing.expect.equal("Bob von Testing <bob@example.org>", mail.header("From"))

        # FIXME: Expect more.

    review.checkMails("Updated Review", checkBobsIssues)

    review.commit("commit #3", nonsense=content(upper={"second"}, skip={"fourth"}))
    review.commit("commit #4", nonsense=content(upper={"second"}, skip={"third"}))
    review.push()

    with frontend.signin("bob"):
        check_locations(review, issue_1, "SECOND")
        check_comment(issue_1, state="open")
        check_locations(review, issue_2, "fifth")
        check_comment(issue_2, state="open")

    review.commit(
        "commit #5", nonsense=content(upper={"second", "fifth"}, skip={"fourth"})
    )
    review.push()

    with frontend.signin("bob"):
        check_locations(review, issue_1, "SECOND")
        check_comment(issue_1, state="open")
        check_locations(review, issue_2, "fifth")
        check_comment(
            issue_2, state="addressed", addressed_by=review.getCommitId(review.sha1s[5])
        )

        issue_3 = frontend.json(
            f"reviews/{review.id}/issues",
            post={
                "text": "Issue on fourth segment",
                "location": get_location(review, review.sha1s[4], "fourth", False),
            },
            check={
                "state": "addressed",
                "addressed_by": review.getCommitId(review.sha1s[5]),
            },
        )["id"]

        frontend.json(
            f"comments/{issue_2}",
            put={
                "draft_changes": {
                    "new_state": "open",
                    "new_location": get_location(
                        review, review.sha1s[5], "FIFTH", False
                    ),
                }
            },
            check={
                "state": "addressed",
                "draft_changes": {
                    "new_state": "open",
                    "new_location": get_location(
                        review, review.sha1s[5], "FIFTH", False
                    ),
                },
            },
        )

        frontend.json(
            f"reviews/{review.id}/batches",
            post={"comment": "Bob's additional work"},
            expect=partial_json(
                {
                    "id": int,
                    "review": review.id,
                    "author": instance.user("bob").id,
                    "comment": int,
                    "created_comments": [issue_3],
                    "reopened_issues": [issue_2],
                }
            ),
        )

    def checkBobsAdditionalWork(mail):
        testing.expect.equal("Bob von Testing <bob@example.org>", mail.header("From"))

        # FIXME: Expect more.

    review.checkMails("Updated Review", checkBobsAdditionalWork)


with repository.workcopy(clone="small") as work:
    test1(work)
