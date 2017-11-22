# @dependency 004-repositories/003-small.py
# @users alice, bob

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": "master"},
    expect=partial_json({"id": int, "name": "master"}),
)

base_sha1 = frontend.json(
    f"commits/{target_branch['head']}", params={"repository": "small"}, extract="sha1"
)


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice")
        review_1.addFilter("bob", "reviewer")
        review_1.addFile(nonsense="nonsense1.txt")
        review_1.commit("Add nonsense\n", nonsense=nonsense("first", "second", "third"))
        review_1.target_branch = target_branch
        review_1.submit()

    markAllAsReviewed(review_1)

    review_branch = review_1.getBranch()
    review_commits = review_1.getBranchCommits()

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={"review": review_1.id},
            expect={
                "id": int,
                "review": review_1.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
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
                "squash": {"requested": False, "message": None, "performed": False},
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


def test2():
    with repository.workcopy(clone="small") as workcopy:
        review_2 = Review(workcopy, "alice", fork_point=base_sha1)
        review_2.addFilter("bob", "reviewer")
        review_2.addFile(nonsense="nonsense2.txt")
        review_2.commit("Add other nonsense", nonsense=nonsense("first"))
        review_2.commit("Add more other nonsense", nonsense=nonsense("second"))
        review_2.commit("Add even more other nonsense", nonsense=nonsense("final"))
        review_2.target_branch = target_branch
        review_2.submit()

    markAllAsReviewed(review_2)

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={"review": review_2.id},
            expect={
                "id": int,
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": False,
                    "strategy_used": None,
                },
                "successful": None,
                "error_message": None,
            },
            extract="id",
        )

        instance.synchronize_service("reviewupdater")

        frontend.json(
            f"reviewintegrationrequests/{integration_id}",
            expect={
                "id": int,
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "merge",
                },
                "successful": True,
                "error_message": None,
            },
        )

        review_branch = review_2.getBranch()
        review_commits = review_2.getBranchCommits()

        testing.expect.check(3, len(review_commits))

        to_head, associated = frontend.json(
            f"branchupdates",
            params={"branch": target_branch["id"], "count": 1},
            expect={
                "branchupdates": [
                    partial_json(
                        from_head=target_branch["head"],
                        to_head=int,
                        associated=list,
                        disassociated=[],
                    )
                ]
            },
            extract={"branchupdates[0]": ("to_head", "associated")},
        )

        merge = frontend.json(
            f"commits/{to_head}",
            params={"repository": "small"},
            expect=partial_json(parents=[target_branch["head"], review_branch["head"]]),
        )

        testing.expect.that(sorted(associated)).equals(
            sorted(commit["id"] for commit in review_commits + [merge])
        )

    target_branch.update(frontend.json(f"branches/{target_branch['id']}"))


def test3():
    with repository.workcopy(clone="small") as workcopy:
        review_3 = Review(workcopy, "alice", fork_point=base_sha1)
        review_3.addFilter("bob", "reviewer")
        review_3.addFile(nonsense="nonsense.txt")
        review_3.commit("Add nonsense", nonsense=nonsense("first"))
        review_3.commit("Add more nonsense", nonsense=nonsense("second"))
        review_3.commit("Add even more nonsense", nonsense=nonsense("final"))
        review_3.target_branch = target_branch
        review_3.submit()

    markAllAsReviewed(review_3)

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={
                "review": review_3.id,
                "squash": {"requested": True, "message": "Add a lot of nonsense"},
            },
            expect={
                "id": int,
                "review": review_3.id,
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
                "review": review_3.id,
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

        # Rebase when the branch history was squashed.
        review_3.expected_partitions.insert(0, {"commits": [], "rebase": int})
        # Rebase when the squash was cherry-picked onto the target branch.
        review_3.expected_partitions.insert(0, {"commits": [], "rebase": int})

        frontend.json(
            f"reviews/{review_3.id}",
            params={"include": "rebases"},
            expect=partial_json(
                partitions=review_3.expected_partitions,
                integration={"state": "performed"},
                linked={
                    "rebases": [
                        {
                            "type": "history-rewrite",
                            "review": review_3.id,
                            "creator": None,
                            "branchupdate": int,
                        },
                        {
                            "type": "move",
                            "review": review_3.id,
                            "creator": None,
                            "branchupdate": int,
                        },
                    ]
                },
            ),
        )

        review_branch = review_3.getBranch()
        review_commits = review_3.getBranchCommits()

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

    review_3.expectMails("Updated Review")
    review_3.expectMails("Updated Review")


with frontend.signin():
    strategy_setting = frontend.json(
        "branchsettings",
        post={
            "branch": target_branch["id"],
            "scope": "integration",
            "name": "strategy",
            "value": ["cherry-pick", "merge"],
        },
    )

try:
    test1()
    test2()
    test3()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)
