# @dependency 004-repositories/003-small.py
# @users alice, bob

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": "master"},
    expect=partial_json({"id": int, "name": "master"}),
)


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice", f"{test.name}/1")
        review_1.addFilter("bob", "reviewer")
        review_1.addFile(nonsense="nonsense.txt")
        review_1.commit("Add nonsense", nonsense=nonsense("first"))
        review_1.commit("Add more nonsense", nonsense=nonsense("second"))
        review_1.commit("Add even more nonsense", nonsense=nonsense("final"))
        review_1.target_branch = target_branch
        review_1.submit()

    markAllAsReviewed(review_1)

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={
                "review": review_1.id,
                "squash": {"requested": True, "message": "Add a lot of nonsense"},
            },
            expect={
                "id": int,
                "review": review_1.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {
                    "requested": True,
                    "message": "Add a lot of nonsense",
                    "performed": False,
                },
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": False,
                    "strategy_used": None,
                },
                "successful": None,
                "error_message": None,
            },
        )["id"]

        instance.synchronize_service("reviewupdater")

        frontend.json(
            f"reviewintegrationrequests/{integration_id}",
            expect={
                "id": int,
                "review": review_1.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {
                    "requested": True,
                    "message": "Add a lot of nonsense",
                    "performed": True,
                },
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "cherry-pick",
                },
                "successful": True,
                "error_message": None,
            },
        )

        review_1.expected_partitions.insert(0, {"commits": [], "rebase": int})

        frontend.json(
            f"reviews/{review_1.id}",
            params={"include": "rebases"},
            expect=partial_json(
                partitions=review_1.expected_partitions,
                integration={"state": "performed"},
                linked={
                    "rebases": [
                        {
                            "type": "history-rewrite",
                            "review": review_1.id,
                            "creator": None,
                            "branchupdate": int,
                        }
                    ]
                },
            ),
        )

        review_branch = review_1.getBranch()
        review_commits = review_1.getBranchCommits()

        testing.expect.check(1, len(review_commits))
        testing.expect.check("Add a lot of nonsense", review_commits[0]["message"])

        branchupdate = frontend.json(
            f"branchupdates",
            params={"branch": target_branch["id"], "count": 1},
            expect={
                "branchupdates": [
                    partial_json(
                        from_head=target_branch["head"],
                        to_head=review_branch["head"],
                        associated=[review_branch["head"]],
                        disassociated=[],
                    )
                ]
            },
        )["branchupdates"][0]

        testing.expect.equal(
            expected=sorted(commit["id"] for commit in review_commits),
            actual=sorted(branchupdate["associated"]),
        )

    target_branch.update(frontend.json(f"branches/{target_branch['id']}"))

    review_1.expectMails("Updated Review")


with frontend.signin():
    strategy_setting = frontend.json(
        "branchsettings",
        post={
            "branch": target_branch["id"],
            "scope": "integration",
            "name": "strategy",
            "value": ["cherry-pick"],
        },
    )

try:
    test1()
    # test2()
    # test3()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)
