# @flag sshd
# @dependency 004-repositories/001-critic.py
# @users alice, bob

# host, _, _ = str(instance.repository_url("alice", via_ssh=True)).partition(":")

# testing.execute.execute([
#     "ssh", "-vvv", "-F", instance.ssh_config(for_user="alice"), "sshd"
# ])

repository.run(
    [
        "push",
        instance.repository_url("alice", via_ssh=True),
        "HEAD:refs/heads/041-ssh/alice/1",
    ]
)

branch_id = frontend.json(
    "branches",
    params={
        "repository": "critic",
        "name": "041-ssh/alice/1",
        "include": "branchupdates",
    },
    expect=partial_json(
        {
            "id": int,
            "repository": instance.repository("critic").id,
            "name": "041-ssh/alice/1",
        }
    ),
)["id"]

frontend.json(
    "branchupdates",
    params={"branch": branch_id},
    expect={
        "branchupdates": [
            partial_json(
                {"id": int, "branch": branch_id, "updater": instance.user("alice").id}
            )
        ]
    },
)

repository.run(
    [
        "push",
        instance.repository_url("bob", via_ssh=True),
        "HEAD:refs/heads/041-ssh/bob/1",
    ]
)

branch_id = frontend.json(
    "branches",
    params={
        "repository": "critic",
        "name": "041-ssh/bob/1",
        "include": "branchupdates",
    },
    expect=partial_json(
        {
            "id": int,
            "repository": instance.repository("critic").id,
            "name": "041-ssh/bob/1",
        }
    ),
)["id"]

frontend.json(
    "branchupdates",
    params={"branch": branch_id},
    expect={
        "branchupdates": [
            partial_json(
                {"id": int, "branch": branch_id, "updater": instance.user("bob").id}
            )
        ]
    },
)
