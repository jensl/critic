# @dependency 004-repositories/003-small.py
# @users alice, bob

import re

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


def test1():
    with repository.workcopy(clone="small") as workcopy:
        review_1 = Review(workcopy, "alice", f"{test.name}/1")
        review_1.addFilter("bob", "reviewer")
        review_1.addFile(nonsense="nonsense1.txt")
        review_1.commit("Add nonsense\n", nonsense=nonsense("first"))
        review_1.commit("Add more nonsense\n", nonsense=nonsense("first", "second"))
        review_1.commit(
            "Add even more nonsense\n", nonsense=nonsense("first", "second", "third")
        )
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
                    "strategy_used": "rebase",
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
                        associated=list,
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
        review_2.addFile(nonsense="nonsense2.txt")
        review_2.commit("Add other nonsense\n", nonsense=nonsense("first"))
        review_2.commit(
            "Add more other nonsense\n", nonsense=nonsense("first", "second")
        )
        review_2.commit(
            "Add even more other nonsense\n",
            nonsense=nonsense("first", "second", "third"),
        )
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
                "id": int,
                "review": review_2.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "rebase",
                },
                "successful": True,
                "error_message": None,
            },
        )

        frontend.json(
            f"reviews/{review_2.id}/rebases",
            expect={
                "rebases": [
                    partial_json(type="move", new_upstream=target_branch["head"])
                ]
            },
        )

        review_branch = review_2.getBranch()
        review_commits = review_2.getBranchCommits()

        testing.expect.equal(expected=3, actual=len(review_commits))

        branchupdate = frontend.json(
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
        )["branchupdates"][0]

        testing.expect.equal(
            expected=sorted(commit["id"] for commit in review_commits),
            actual=sorted(branchupdate["associated"]),
        )

        review_2.expectMails("Updated Review")

    target_branch.update(frontend.json(f"branches/{target_branch['id']}"))


def test3():
    with repository.workcopy(clone="small") as workcopy:
        review_3 = Review(workcopy, "alice", f"{test.name}/3")
        review_3.addFilter("bob", "reviewer")
        review_3.addFile(conflict="nonsense1.txt", nonsense="nonsense3.txt")
        review_3.commit("Add safe nonsense\n", nonsense=nonsense("first"))
        conflicting_sha1 = review_3.commit(
            "Add conflicting nonsense\n",
            conflict=nonsense("conflict"),
            nonsense=nonsense("second"),
        )
        review_3.commit("Add more safe nonsense\n", nonsense=nonsense("third"))
        review_3.target_branch = target_branch
        review_3.submit()

    markAllAsReviewed(review_3)

    with frontend.signin("alice"):
        integration_id = frontend.json(
            "reviewintegrationrequests",
            post={"review": review_3.id},
            expect={
                "id": int,
                "review": review_3.id,
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

        req = frontend.json(
            f"reviewintegrationrequests/{integration_id}",
            expect={
                "id": integration_id,
                "review": review_3.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "rebase",
                },
                "successful": False,
                "error_message": re.compile(
                    (cherrypick_pattern + status_pattern + diff_pattern).format(
                        sha1=conflicting_sha1,
                        situation=r"You are currently cherry-picking commit \1",
                        continue_command="git cherry-pick --continue",
                        abort_instruction=(
                            'use "git cherry-pick --abort" to cancel the cherry-pick '
                            "operation"
                        ),
                        test_name=test.name,
                        modified=r"nonsense3\.txt",
                        conflicted=r"nonsense1\.txt",
                        trailing=r"\1\.\.\. Add conflicting nonsense",
                    )
                ),
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
            "value": ["rebase"],
        },
    )

try:
    test1()
    test2()
    test3()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)
