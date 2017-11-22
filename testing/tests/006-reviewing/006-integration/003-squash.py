# @dependency 004-repositories/003-small.py
# @user alice

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": "master"},
    expect=partial_json({"id": int, "name": "master"}),
)


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice", f"{test.name}/1")
        review_1.addFile(nonsense="nonsense.txt")
        review_1.commit("Add nonsense", nonsense=nonsense("first"))
        review_1.commit("Add more nonsense", nonsense=nonsense("second"))
        review_1.commit("Add even more nonsense", nonsense=nonsense("final"))
        review_1.target_branch = target_branch
        review_1.submit()

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={
                "review": review_1.id,
                "squash": {"requested": True, "message": "Add a lot of nonsense"},
                "integration": {"requested": False},
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
                    "requested": False,
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
                    "requested": False,
                    "performed": False,
                    "strategy_used": None,
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
                integration={"state": "planned"},
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

        commits = frontend.json(f"branches/{review_1.json['branch']}/commits")[
            "commits"
        ]

        testing.expect.check(1, len(commits))
        testing.expect.check("Add a lot of nonsense", commits[0]["message"])

    review_1.expectMails("Updated Review")


test1()
