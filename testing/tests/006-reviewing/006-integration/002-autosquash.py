# @dependency 004-repositories/003-small.py

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": "master"},
    expect=partial_json({"id": int, "name": "master"}),
)


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice", f"{test.name}/1")
        review_1.addFile(nonsense="nonsense.txt")
        review_1.commit("Add nonsense\n", nonsense=nonsense("first"))
        review_1.commit("fixup! Add nonsense\n", nonsense=nonsense("second"))
        review_1.commit("fixup! Add nonsense\n", nonsense=nonsense("final"))
        review_1.target_branch = target_branch
        review_1.submit()

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={
                "review": review_1.id,
                "autosquash": {"requested": True},
                "integration": {"requested": False},
            },
            expect={
                "id": int,
                "review": review_1.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": True, "performed": False},
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
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": True, "performed": True},
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
                {
                    "partitions": review_1.expected_partitions,
                    "integration": {"state": "planned"},
                    "linked": {
                        "rebases": [
                            {
                                "type": "history-rewrite",
                                "review": review_1.id,
                                "creator": None,
                                "branchupdate": int,
                            }
                        ]
                    },
                }
            ),
        )

        commits = frontend.json(f"branches/{review_1.json['branch']}/commits")[
            "commits"
        ]

        testing.expect.equal(1, len(commits))
        testing.expect.equal("Add nonsense\n", commits[0]["message"])

    review_1.expectMails("Updated Review")


def test2():
    with repository.workcopy(clone="small") as workcopy:
        review_2 = Review(workcopy, "alice", f"{test.name}/2")
        review_2.addFile(nonsense="nonsense.txt")
        review_2.commit("Add nonsense\n", nonsense=nonsense("first"))
        review_2.commit("fixup! Add nonsense\n", nonsense=nonsense("second"))
        review_2.commit("Rewrite nonsense\n", nonsense=nonsense("rewrite"))
        conflicting_sha1 = review_2.commit(
            "fixup! Add nonsense\n", nonsense=nonsense("final")
        )
        review_2.target_branch = target_branch
        review_2.submit()

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={
                "review": review_2.id,
                "autosquash": {"requested": True},
                "integration": {"requested": False},
            },
            expect={
                "id": int,
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": True, "performed": False},
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
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": True, "performed": True},
                "integration": {
                    "requested": False,
                    "performed": False,
                    "strategy_used": None,
                },
                "successful": False,
                "error_message": re.compile(
                    f"""\
=== git rebase -i --autosquash [0-9a-f]{{40}} ===
error: could not apply [0-9a-f]{{4,40}}... fixup! Add nonsense
.*


=== git status ===
.*
\tboth modified:   {test.name}/nonsense.txt
.*


=== git diff ===
.*
""",
                    re.DOTALL,
                ),
            },
        )

        commits = frontend.json(f"branches/{review_2.json['branch']}/commits")[
            "commits"
        ]

        testing.expect.equal(4, len(commits))
        testing.expect.equal("fixup! Add nonsense\n", commits[0]["message"])
        testing.expect.equal("Rewrite nonsense\n", commits[1]["message"])
        testing.expect.equal("fixup! Add nonsense\n", commits[2]["message"])
        testing.expect.equal("Add nonsense\n", commits[3]["message"])


test1()
test2()
