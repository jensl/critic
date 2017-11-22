# @dependency 004-repositories/003-small.py

import os

target_branch = frontend.json(
    "branches",
    params={"repository": "small", "name": "master"},
    expect=partial_json({"id": int, "name": "master"}),
)

with repository.workcopy(clone="small") as workcopy:
    review_1 = Review(workcopy, "alice", f"{test.name}/1")
    review_1.addFile(nonsense="nonsense.txt")
    review_1.commit("More nonsense", nonsense=nonsense("review_1"))
    review_1.target_branch = target_branch
    review_1.submit()

    frontend.json(
        f"reviews/{review_1.id}",
        expect=partial_json(
            {
                "integration": {
                    "target_branch": target_branch["id"],
                    "commits_behind": 0,
                    "state": "planned",
                    "squashed": None,
                    "autosquashed": None,
                    "strategy_used": None,
                    "conflicts": [],
                    "error_message": None,
                }
            }
        ),
    )

    workcopy.run(["checkout", "master"])
    os.mkdir(os.path.join(workcopy.path, test.name))
    with open(os.path.join(workcopy.path, f"{test.name}/unrelated.txt"), "w") as file:
        print(nonsense("master_1"), file=file)
    workcopy.run(["add", f"{test.name}/unrelated.txt"])
    workcopy.run(["commit", "-mUnrelated change #1"])
    workcopy.run(["push", review_1.repository_url, "master"])

    instance.synchronize_service("branchupdater", "reviewupdater")

    frontend.json(
        f"reviews/{review_1.id}",
        expect=partial_json({"integration": {"commits_behind": 1, "conflicts": []}}),
    )

    review_2 = Review(workcopy, "alice", f"{test.name}/2")
    review_2.addFile(unrelated="unrelated.txt")
    review_2.commit("More nonsense", unrelated=nonsense("review_2"))
    review_2.target_branch = target_branch
    review_2.submit()

    frontend.json(
        f"reviews/{review_2.id}",
        expect=partial_json(
            {
                "integration": {
                    "target_branch": target_branch["id"],
                    "commits_behind": 0,
                    "state": "planned",
                    "squashed": None,
                    "autosquashed": None,
                    "strategy_used": None,
                    "conflicts": [],
                    "error_message": None,
                }
            }
        ),
    )

    workcopy.run(["checkout", "master"])
    with open(os.path.join(workcopy.path, f"{test.name}/unrelated.txt"), "w") as file:
        print(nonsense("master_2"), file=file)
    workcopy.run(["add", f"{test.name}/unrelated.txt"])
    workcopy.run(["commit", "-mUnrelated change #2"])
    workcopy.run(["push", review_2.repository_url, "master"])

    instance.synchronize_service("branchupdater", "reviewupdater")

    frontend.json(
        f"reviews/{review_1.id}",
        expect=partial_json({"integration": {"commits_behind": 2, "conflicts": []}}),
    )

    frontend.json(
        f"reviews/{review_2.id}",
        expect=partial_json(
            {
                "integration": {
                    "commits_behind": 1,
                    "conflicts": [review_2.getFileId("unrelated")],
                }
            }
        ),
    )
