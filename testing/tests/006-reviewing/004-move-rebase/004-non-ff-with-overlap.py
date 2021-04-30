# @users alice, bob


def test1(work):
    """Basic non-fast-forward move rebase with overlapping work."""

    review = Review(work, "alice", "039-move-rebase/004-non-ff-with-overlap")
    review.addFile(nonsense="039-move-rebase/004-non-ff-with-overlap/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit(
        "reference #1", nonsense=content("one", "two", "three"), reference=True
    )
    review.commit(
        "reference #2", nonsense=content("one", "two", "three", "four"), reference=True
    )
    review.commit("commit #1", nonsense=content("one", "TWO", "three"))
    review.commit("commit #2", nonsense=content("ONE", "TWO", "three"))
    review.commit("commit #3", nonsense=content("ONE", "TWO", "THREE"))
    review.submit()

    def commit_ids(sha1s):
        return [review.getCommitId(sha1) for sha1 in sha1s]

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": commit_ids(reversed(review.sha1s[-3:])), "rebase": None}
                ],
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ]
                },
            }
        ),
    )

    review.push_reference_branch()

    with frontend.signin("alice"):
        rebase_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"new_upstream": review.sha1s[0]},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "branchupdate": None,
                "type": "move",
                "old_upstream": review.getCommitId(review.sha1s[1]),
                "new_upstream": review.getCommitId(review.sha1s[0]),
                "equivalent_merge": None,
                "replayed_rebase": None,
            },
        )["id"]

    review.reset(review.sha1s[0])
    review.commit("rebased #1", nonsense=content("one", "TWO", "three", "four"))
    review.commit("rebased #2", nonsense=content("ONE", "TWO", "three", "four"))
    review.commit("rebased #3", nonsense=content("ONE", "TWO", "THREE", "four"))
    review.push(move_rebase=True)

    frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": [], "rebase": rebase_id},
                    {
                        "commits": commit_ids(reversed(review.sha1s[2:5])),
                        "rebase": None,
                    },
                ],
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[-1]),
                            }
                        )
                    ],
                    "rebases": [
                        {
                            "id": rebase_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "move",
                            "old_upstream": review.getCommitId(review.sha1s[1]),
                            "new_upstream": review.getCommitId(review.sha1s[0]),
                            "equivalent_merge": None,
                            "replayed_rebase": int,
                        }
                    ],
                },
            }
        ),
    )


with repository.workcopy(clone="small") as work:
    test1(work)