# @dependency 004-repositories/003-small.py
# @users alice, bob, dave, erin


def get_assigned_files(mail):
    result = None
    for line in mail.lines:
        if result is None:
            if line == "The following still pending changes are assigned to you:":
                result = {}
            continue
        line = line.strip()
        if not line:
            return result
        filename, counts = line.split()
        result[filename] = counts


with repository.workcopy(clone="small") as work:
    review = Review(work, "alice")
    review.addFile(nonsense1=f"first.txt")
    review.addFile(nonsense2=f"second.txt")
    review.addFilter("bob", "reviewer", f"{test.name}/")
    review.addFilter("dave", "reviewer", f"{test.name}/second.txt")
    review.addFilter("erin", "watcher", "/")
    review.commit("commit #1", nonsense1=nonsense("one"), nonsense2=nonsense("ONE"))
    review.commit("commit #2", nonsense1=nonsense("two"), nonsense2=nonsense("TWO"))
    review.commit("commit #3", nonsense1=nonsense("final"), nonsense2=nonsense("FINAL"))
    review.submit()

frontend.json(
    f"reviews/{review.id}/reviewpings", expect=partial_json({"reviewpings": []})
)


def ping_review(message, recipients, checker):
    with frontend.signin("alice"):
        frontend.json(
            "reviewpings",
            post={"review": review.id, "message": message},
            params={"include": "reviewevents"},
            expect={
                "event": int,
                "message": message,
                "linked": {
                    "reviewevents": [
                        partial_json(
                            {"type": "pinged", "user": instance.user("alice").id}
                        )
                    ]
                },
            },
        )
    review.checkMails("Pinged Review", checker, recipients=recipients)


def check_first_ping(mail):
    testing.expect.true("Alice von Testing has pinged the review!" in mail.lines)
    testing.expect.true("  This is the first ping!" in mail.lines)

    assigned_files = get_assigned_files(mail)
    if mail.recipient == "bob@example.org":
        expected_files = {
            f"{test.name}/first.txt": "-16/+24",
            f"{test.name}/second.txt": "-16/+24",
        }
    else:
        expected_files = {f"{test.name}/second.txt": "-16/+24"}
    testing.expect.equal(expected_files, assigned_files)


def check_second_ping(mail):
    testing.expect.true("Alice von Testing has pinged the review!" in mail.lines)
    testing.expect.true("  This is the second ping!" in mail.lines)

    assigned_files = get_assigned_files(mail)
    expected_files = {f"{test.name}/first.txt": "-16/+24"}
    testing.expect.equal(expected_files, assigned_files)


ping_review("This is the first ping!", ["bob", "dave"], check_first_ping)


with frontend.signin("dave"):
    frontend.json(
        "reviewablefilechanges",
        put={"draft_changes": {"new_is_reviewed": True}},
        params={"review": review.id, "assignee": "(me)", "state": "pending"},
    )
    frontend.json("batches", post={}, params={"review": review.id})
review.expectMails("Updated Review")

ping_review("This is the second ping!", ["bob"], check_second_ping)

with frontend.signin("bob"):
    frontend.json(
        "reviewablefilechanges",
        put={"draft_changes": {"new_is_reviewed": True}},
        params={"review": review.id, "assignee": "(me)", "state": "pending"},
    )
    frontend.json("batches", post={}, params={"review": review.id})
review.expectMails("Updated Review")

with frontend.signin("alice"):
    frontend.json(
        "reviewpings",
        post={"review": review.id, "message": "This ping should not be allowed!"},
        expected_http_status=400,
        expect=expected_error(
            title="Invalid API request",
            message="There are no (relevant) reviewers to ping!",
        ),
    )
