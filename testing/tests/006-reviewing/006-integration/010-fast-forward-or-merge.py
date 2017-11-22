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
        review_1 = Review(workcopy, "alice", fork_point=base_sha1)
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
                    "strategy_used": "fast-forward",
                },
                "successful": True,
                "error_message": None,
            },
        )

        review_branch = review_1.getBranch()
        review_commits = review_1.getBranchCommits()

        testing.expect.check(3, len(review_commits))

        associated = frontend.json(
            f"branchupdates",
            params={"branch": target_branch["id"], "count": 1},
            expect={
                "branchupdates": [
                    partial_json(
                        from_head=target_branch["head"],
                        to_head=review_branch["head"],
                        associated=list,
                        disassociated=[],
                    )
                ]
            },
            extract="branchupdates[0].associated",
        )

        testing.expect.equal(
            expected=sorted(commit["id"] for commit in review_commits),
            actual=sorted(associated),
        )

    target_branch.update(frontend.json(f"branches/{target_branch['id']}"))


def test2():
    with repository.workcopy(clone="small") as workcopy:
        review_2 = Review(workcopy, "alice", fork_point=base_sha1)
        review_2.addFilter("bob", "reviewer")
        review_2.addFile(nonsense="nonsense.txt")
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


with frontend.signin():
    strategy_setting = frontend.json(
        "branchsettings",
        post={
            "branch": target_branch["id"],
            "scope": "integration",
            "name": "strategy",
            "value": ["fast-forward", "merge"],
        },
    )

try:
    test1()
    test2()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)
