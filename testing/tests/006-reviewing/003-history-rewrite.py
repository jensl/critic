# @dependency 004-repositories/003-small.py
# @users alice, bob


def test1(work):
    """Basic rewrite, squashing 3 commits into one, at the same upstream."""

    review = Review(work, "alice", "038-history-rewrite/1")
    review.addFile(nonsense="038-history-rewrite/1/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit("reference", nonsense=nonsense("ref"), reference=True)
    review.commit("commit #1", nonsense=nonsense("one"))
    review.commit("commit #2", nonsense=nonsense("two"))
    review.commit("commit #3", nonsense=nonsense("final"))
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

    with frontend.signin("alice"):
        rebase_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"history_rewrite": True},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "type": "history-rewrite",
                "branchupdate": None,
            },
        )["id"]

    review.reset()
    review.commit("commit #X", nonsense=nonsense("final"))
    review.push(history_rewrite=True)

    result = frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": [], "rebase": rebase_id},
                    {
                        "commits": commit_ids(reversed(review.sha1s[-4:-1])),
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
                            "type": "history-rewrite",
                        }
                    ],
                },
            }
        ),
    )

    branch = result["linked"]["branches"][0]

    frontend.json(
        f"branches/{branch['id']}/commits",
        expect={
            "commits": [partial_json({"sha1": review.sha1s[review.last_pushed_commit]})]
        },
    )

    frontend.json(
        f"branches/{branch['id']}/commits",
        params={"scope": "upstreams"},
        expect={
            "commits": [
                partial_json({"sha1": review.sha1s[review.last_reference_commit]})
            ]
        },
    )


def test2(work):
    """Rewrite that drops a commit+revert pair, resetting the review branch back
       to a previous state."""

    review = Review(work, "alice", "038-history-rewrite/2")
    review.addFile(nonsense="038-history-rewrite/2/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit("reference", nonsense=nonsense("ref"), reference=True)
    review.commit("commit #1", nonsense=nonsense("one"))
    review.commit("commit #2", nonsense=nonsense("two"))
    review.commit("revert commit #2", nonsense=nonsense("one"))
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

    with frontend.signin("alice"):
        rebase_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"history_rewrite": True},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "type": "history-rewrite",
                "branchupdate": None,
            },
        )["id"]

    review.reset(review.sha1s[1])
    review.push(history_rewrite=True)

    result = frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": [], "rebase": rebase_id},
                    {
                        "commits": commit_ids(reversed(review.sha1s[-3:])),
                        "rebase": None,
                    },
                ],
                "linked": {
                    "branches": [
                        partial_json(
                            {
                                "name": review.review_branch_name,
                                "head": review.getCommitId(review.sha1s[1]),
                            }
                        )
                    ],
                    "rebases": [
                        {
                            "id": rebase_id,
                            "review": review.id,
                            "creator": instance.userid("alice"),
                            "branchupdate": int,
                            "type": "history-rewrite",
                        }
                    ],
                },
            }
        ),
    )

    branch = result["linked"]["branches"][0]

    frontend.json(
        f"branches/{branch['id']}/commits",
        expect={"commits": [partial_json({"sha1": review.sha1s[1]})]},
    )

    frontend.json(
        f"branches/{branch['id']}/commits",
        params={"scope": "upstreams"},
        expect={
            "commits": [
                partial_json({"sha1": review.sha1s[review.last_reference_commit]})
            ]
        },
    )


def test3(work):
    """Rewrite that actually rebases onto a newer upstream, where some changes
       have been integrated. (This is not really a proper "pure" history
       rewrite, but it's a sometimes occuring use-case.)"""

    review = Review(work, "alice", "038-history-rewrite/3")
    review.addFile(nonsense="038-history-rewrite/3/nonsense.txt")
    review.addFilter("bob", "reviewer", "/")
    review.commit("reference", nonsense=nonsense("ref"), reference=True)
    review.commit("commit #1", nonsense=nonsense("ref", "one"))
    review.commit("commit #2", nonsense=nonsense("ref", "one", "two"))
    review.commit("commit #3", nonsense=nonsense("ref", "one", "two", "three"))
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

    with frontend.signin("alice"):
        rebase_id = frontend.json(
            f"reviews/{review.id}/rebases",
            post={"history_rewrite": True},
            expect={
                "id": int,
                "review": review.id,
                "creator": instance.userid("alice"),
                "type": "history-rewrite",
                "branchupdate": None,
            },
        )["id"]

    review.commit("integrated #1", nonsense=nonsense("ref", "one"), reference=True)
    review.commit(
        "integrated #2", nonsense=nonsense("ref", "one", "two"), reference=True
    )

    review.reset()
    review.commit("rebased #3", nonsense=nonsense("ref", "one", "two", "three"))
    review.push(history_rewrite=True)

    result = frontend.json(
        f"reviews/{review.id}",
        params={"include": "branches,rebases"},
        expect=partial_json(
            {
                "partitions": [
                    {"commits": [], "rebase": rebase_id},
                    {
                        "commits": commit_ids(reversed(review.sha1s[-6:-3])),
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
                            "type": "history-rewrite",
                        }
                    ],
                },
            }
        ),
    )

    branch = result["linked"]["branches"][0]

    frontend.json(
        f"branches/{branch['id']}/commits",
        expect={
            "commits": [partial_json({"sha1": review.sha1s[review.last_pushed_commit]})]
        },
    )

    frontend.json(
        f"branches/{branch['id']}/commits",
        params={"scope": "upstreams"},
        expect={
            "commits": [
                partial_json({"sha1": review.sha1s[review.last_reference_commit]})
            ]
        },
    )


with repository.workcopy(clone="small") as work:
    test1(work)
    test2(work)
    test3(work)
