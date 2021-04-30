# @dependency 004-repositories/003-small.py
# @users alice, bob

import re

target_branch_name = f"{test.name}/target"

with repository.workcopy(clone="small") as workcopy:
    workcopy.run(["checkout", "-b", target_branch_name, "master"])
    workcopy.commit("Base commit")
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
        review_1 = Review(workcopy, "alice")
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
                    "strategy_used": "merge",
                },
                "successful": True,
                "error_message": None,
            },
        )

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
            extract=("branchupdates[0].to_head", "branchupdates[0].associated"),
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


# Like test1(), but a review based on the tip of its target branch, checking
# that a merge commit is still created.
def test2():
    with repository.workcopy(clone="small") as workcopy:
        review_2 = Review(
            workcopy,
            "alice",
            f"{test.name}/2",
            fork_point=f"origin/{target_branch_name}",
        )
        review_2.addFilter("bob", "reviewer")
        review_2.addFile(nonsense="nonsense2.txt")
        review_2.commit("Add nonsense\n", nonsense=nonsense("first"))
        review_2.commit("Add more nonsense\n", nonsense=nonsense("first", "second"))
        review_2.commit(
            "Add even more nonsense\n", nonsense=nonsense("first", "second", "third")
        )
        review_2.target_branch = target_branch
        review_2.submit()

    markAllAsReviewed(review_2)

    review_branch = review_2.getBranch()
    review_commits = review_2.getBranchCommits()

    testing.expect.that(review_2.json["integration"]["commits_behind"]).equals(0)

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

        branchupdate = frontend.json(
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
            extract="branchupdates[0]",
        )

        merge = frontend.json(
            f"commits/{branchupdate['to_head']}",
            params={"repository": "small"},
            expect=partial_json(parents=[target_branch["head"], review_branch["head"]]),
        )

        testing.expect.that(sorted(branchupdate["associated"])).equals(
            sorted(commit["id"] for commit in review_commits + [merge])
        )

    target_branch.update(frontend.json(f"branches/{target_branch['id']}"))


def test3():
    with repository.workcopy(clone="small") as workcopy:
        review_3 = Review(workcopy, "alice")
        review_3.addFilter("bob", "reviewer")
        review_3.addFile(nonsense1="nonsense1.txt", nonsense3="nonsense3.txt")
        review_3.commit("Add innocent nonsense\n", nonsense3=nonsense("first"))
        review_3.commit("Add conflicting nonsense\n", nonsense1=nonsense("conflict"))
        conflicting_sha1 = review_3.commit(
            "Add more innocent nonsense\n", nonsense3=nonsense("first", "second")
        )
        review_3.target_branch = target_branch
        review_3.submit()

    markAllAsReviewed(review_3)

    review_branch = review_3.getBranch()
    review_commits = review_3.getBranchCommits()

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
            extract="id",
        )

        instance.synchronize_service("reviewupdater")

        frontend.json(
            f"reviewintegrationrequests/{integration_id}",
            expect={
                "id": int,
                "review": review_3.id,
                "target_branch": target_branch["id"],
                "branchupdate": int,
                "squash": {"requested": False, "message": None, "performed": False},
                "autosquash": {"requested": False, "performed": False},
                "integration": {
                    "requested": True,
                    "performed": True,
                    "strategy_used": "merge",
                },
                "successful": False,
                "error_message": re.compile(
                    (merge_pattern + status_pattern + diff_pattern).format(
                        sha1=conflicting_sha1,
                        situation=r"You have unmerged paths",
                        continue_command="git commit",
                        abort_instruction='use "git merge --abort" to abort the merge',
                        test_name=test.name,
                        modified=r"nonsense3\.txt",
                        conflicted=r"nonsense1\.txt",
                        trailing=conflicting_sha1,
                    )
                ),
            },
        )


with frontend.signin():
    strategy_setting = frontend.json(
        "branchsettings",
        post={
            "branch": target_branch["id"],
            "scope": "integration",
            "name": "strategy",
            "value": ["merge"],
        },
    )

try:
    test1()
    test2()
    test3()
finally:
    with frontend.signin():
        frontend.json(f"branchsettings/{strategy_setting['id']}", delete=True)