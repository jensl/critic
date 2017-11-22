# @dependency 004-repositories/003-small.py
# @users alice, bob


target_branch_name = f"{test.name}/target"

with repository.workcopy(clone="small") as workcopy:
    workcopy.run(["checkout", "-b", target_branch_name, "master"])
    workcopy.run(
        [
            "push",
            "-u",
            instance.repository_url("alice", repository=workcopy.clone_of),
            "HEAD",
        ]
    )

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": target_branch_name},
    expect=partial_json({"id": int, "name": target_branch_name}),
)
testing.logger.debug(repr(target_branch))


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice", f"{test.name}/1")
        review_1.addFilter("bob", "reviewer")
        review_1.addFile(nonsense="nonsense.txt")
        review_1.commit("Add nonsense\n", nonsense=nonsense("first"))
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
                    "strategy_used": "fast-forward",
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
        review_2 = Review(workcopy, "alice", f"{test.name}/2")
        review_2.addFilter("bob", "reviewer")
        review_2.addFile(nonsense="nonsense.txt")
        review_2.commit("Add more nonsense\n", nonsense=nonsense("first"))
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
        )["id"]

        instance.synchronize_service("reviewupdater")

        frontend.json(
            f"reviewintegrationrequests/{integration_id}",
            expect={
                "id": integration_id,
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "fast-forward",
                },
                "successful": False,
                "error_message": "must be fast-forward",
            },
        )

        branchupdate = frontend.json(
            f"branchupdates",
            params={"branch": target_branch["id"], "count": 1},
            expect={"branchupdates": [partial_json(to_head=target_branch["head"])]},
        )["branchupdates"][0]


with frontend.signin():
    strategy_setting = frontend.json(
        "branchsettings",
        post={
            "branch": target_branch["id"],
            "scope": "integration",
            "name": "strategy",
            "value": ["fast-forward"],
        },
    )

try:
    test1()
    test2()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)
