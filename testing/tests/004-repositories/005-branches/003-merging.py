# @dependency 004-repositories/003-small.py

import os

PREFIX = test.name + "/"
FILENAME = test.name + "-{}.txt"


def commit(work, filename, message):
    with open(os.path.join(work.path, filename), "w") as file:
        print(message, file=file)
    work.run(["add", filename])
    work.run(["commit", "-m" + message])
    return work.run(["rev-parse", "HEAD"]).strip()


def check_branch(branch_name, **kwargs):
    return frontend.json(
        "branches",
        params={"repository": "small", "name": branch_name},
        expect=partial_json(kwargs),
    )


with repository.workcopy(clone="small") as work:
    repository_url = instance.repository_url("alice", repository=work.clone_of)
    prefix = PREFIX + "test1/"

    work.run(["checkout", "-b", prefix + "base"])
    base_sha1s = [
        commit(work, FILENAME.format("base"), "test1/base, commit1"),
        commit(work, FILENAME.format("base"), "test1/base, commit2"),
        commit(work, FILENAME.format("base"), "test1/base, commit3"),
    ]
    work.run(["push", "-u", repository_url, prefix + "base"])

    base_id = check_branch(prefix + "base", size=3, is_merged=False)["id"]

    work.run(["checkout", "-b", prefix + "topic", base_sha1s[1]])
    topic_sha1s = [
        commit(work, FILENAME.format("topic"), "test1/topic, commit1"),
        commit(work, FILENAME.format("topic"), "test1/topic, commit2"),
        commit(work, FILENAME.format("topic"), "test1/topic, commit3"),
    ]
    work.run(["push", "-u", repository_url, prefix + "topic"])

    topic_id = check_branch(
        prefix + "topic", base_branch=base_id, size=3, is_merged=False
    )["id"]

    work.run(["checkout", prefix + "base"])
    work.run(["merge", prefix + "topic"])
    work.run(["push", repository_url])

    check_branch(prefix + "base", size=7, is_merged=False)
    check_branch(prefix + "topic", base_branch=base_id, size=3, is_merged=True)
