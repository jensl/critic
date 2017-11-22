# @dependency 004-repositories/003-small.py
# @users alice, bob, dave

with repository.workcopy(clone="small") as work:
    review = Review(work, "alice", test.name)
    review.addFile(
        first=f"{test.name}/first.txt",
        second=f"{test.name}/second.txt",
        third=f"{test.name}/third.txt",
    )
    review.commit(
        "Reference commit",
        first=nonsense("reference"),
        second=nonsense("reference"),
        third=nonsense("reference"),
        reference=True,
    )
    review.commit(
        "First commit",
        first=nonsense("#1"),
        second=nonsense("#1"),
        third=nonsense("#1"),
    )
    review.commit(
        "Second commit",
        first=nonsense("#2"),
        second=nonsense("#2"),
        third=nonsense("#2"),
    )
    review.addFilter("bob", "reviewer", f"{test.name}/")
    review.addFilter("dave", "reviewer", f"{test.name}/")
    review.submit()

bob = instance.user("bob")
dave = instance.user("dave")

first_id = review.getFileId("first")
second_id = review.getFileId("second")
third_id = review.getFileId("third")

changeset_ids = frontend.json(
    f"reviews/{review.id}", expect=partial_json({"changesets": [int, int]})
)["changesets"]


def rfcs(common={}, unique={}):
    return unordered_list(
        key=("changeset", "file"),
        expected={
            (changeset_ids[0], first_id): unique.get((changeset_ids[0], first_id), {}),
            (changeset_ids[0], second_id): unique.get(
                (changeset_ids[0], second_id), {}
            ),
            (changeset_ids[0], third_id): unique.get((changeset_ids[0], third_id), {}),
            (changeset_ids[1], first_id): unique.get((changeset_ids[1], first_id), {}),
            (changeset_ids[1], second_id): unique.get(
                (changeset_ids[1], second_id), {}
            ),
            (changeset_ids[1], third_id): unique.get((changeset_ids[1], third_id), {}),
        },
        **{"*": "*"},
        **common,
    )


frontend.json(
    f"reviews/{review.id}/reviewablefilechanges",
    expect={
        "reviewablefilechanges": rfcs(common={"is_reviewed": False, "reviewed_by": []})
    },
)


def make_change(changeset_id, file_id, new_is_reviewed):
    draft_before = frontend.json(
        f"reviews/{review.id}/reviewablefilechanges",
        params={"changeset": changeset_id, "file": file_id},
        expect={"reviewablefilechanges": [dict]},
    )["reviewablefilechanges"][0]["draft_changes"]

    if draft_before is None:
        expect_draft_changes = {"new_is_reviewed": new_is_reviewed}
    else:
        expect_draft_changes = None

    frontend.json(
        f"reviews/{review.id}/reviewablefilechanges",
        params={"changeset": changeset_id, "file": file_id},
        put={"draft_changes": {"new_is_reviewed": new_is_reviewed}},
        expect={
            "reviewablefilechanges": [
                partial_json({"draft_changes": expect_draft_changes})
            ]
        },
    )


def submit_changes():
    frontend.json(f"reviews/{review.id}/batches", post={})
    review.expectMails("Updated Review")


with frontend.signin("bob"):
    make_change(changeset_ids[0], first_id, True)
    make_change(changeset_ids[0], second_id, True)
    submit_changes()

frontend.json(
    f"reviews/{review.id}/reviewablefilechanges",
    expect={
        "reviewablefilechanges": rfcs(
            common={"is_reviewed": False, "reviewed_by": []},
            unique={
                (changeset_ids[0], first_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
                (changeset_ids[0], second_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
            },
        )
    },
)

with frontend.signin("dave"):
    make_change(changeset_ids[0], second_id, True)
    make_change(changeset_ids[0], third_id, True)
    submit_changes()

frontend.json(
    f"reviews/{review.id}/reviewablefilechanges",
    expect={
        "reviewablefilechanges": rfcs(
            common={"is_reviewed": False, "reviewed_by": []},
            unique={
                (changeset_ids[0], first_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
                (changeset_ids[0], second_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id, dave.id],
                },
                (changeset_ids[0], third_id): {
                    "is_reviewed": True,
                    "reviewed_by": [dave.id],
                },
            },
        )
    },
)

with frontend.signin("dave"):
    make_change(changeset_ids[0], second_id, False)
    submit_changes()

frontend.json(
    f"reviews/{review.id}/reviewablefilechanges",
    expect={
        "reviewablefilechanges": rfcs(
            common={"is_reviewed": False, "reviewed_by": []},
            unique={
                (changeset_ids[0], first_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
                (changeset_ids[0], second_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
                (changeset_ids[0], third_id): {
                    "is_reviewed": True,
                    "reviewed_by": [dave.id],
                },
            },
        )
    },
)

with frontend.signin("bob"):
    make_change(changeset_ids[0], second_id, False)
    submit_changes()

frontend.json(
    f"reviews/{review.id}/reviewablefilechanges",
    expect={
        "reviewablefilechanges": rfcs(
            common={"is_reviewed": False, "reviewed_by": []},
            unique={
                (changeset_ids[0], first_id): {
                    "is_reviewed": True,
                    "reviewed_by": [bob.id],
                },
                (changeset_ids[0], second_id): {
                    "is_reviewed": False,
                    "reviewed_by": [],
                },
                (changeset_ids[0], third_id): {
                    "is_reviewed": True,
                    "reviewed_by": [dave.id],
                },
            },
        )
    },
)
