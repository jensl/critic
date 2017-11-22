# @dependency 001-install.py
# @dependency 004-repositories/003-small.py
# @users alice

branch_id = frontend.json(
    "branches", params={"repository": "small", "name": "master"}, extract="id"
)

with frontend.signin():
    settings = frontend.json("branchsettings", expect={"branchsettings": []})

    first = frontend.json(
        "branchsettings",
        post={
            "branch": branch_id,
            "scope": "testing",
            "name": "first",
            "value": "first value",
        },
        expect={
            "id": int,
            "branch": branch_id,
            "scope": "testing",
            "name": "first",
            "value": "first value",
        },
    )

    first = frontend.json(
        "branchsettings/%d" % first["id"],
        put={"value": "first value (edited)"},
        expect={
            "id": first["id"],
            "branch": branch_id,
            "scope": "testing",
            "name": "first",
            "value": "first value (edited)",
        },
    )

    frontend.json(
        "branchsettings",
        post={"branch": branch_id, "scope": "testing", "name": "first", "value": 4711},
        expected_http_status=400,
        expect={
            "error": partial_json(
                message="Branch setting already defined: testing:first"
            )
        },
    )

    second = frontend.json(
        f"branches/{branch_id}/branchsettings",
        params={"scope": "testing", "name": "second"},
        put={"value": 4711},
        expected_http_status=404,
        expect={
            "error": partial_json(message="Branch setting not defined: testing:second")
        },
    )

    second = frontend.json(
        f"branches/{branch_id}/branchsettings",
        post={"scope": "testing", "name": "second", "value": "second value"},
        expect={
            "id": int,
            "branch": branch_id,
            "scope": "testing",
            "name": "second",
            "value": "second value",
        },
    )

    second = frontend.json(
        f"branches/{branch_id}/branchsettings",
        params={"scope": "testing", "name": "second"},
        put={"value": "second value (edited)"},
        expect={
            "id": second["id"],
            "branch": branch_id,
            "scope": "testing",
            "name": "second",
            "value": "second value (edited)",
        },
    )

    frontend.json(
        f"branches/{branch_id}/branchsettings",
        params={"scope": "testing"},
        expect={"branchsettings": [first, second]},
    )

    frontend.json("branchsettings/%d" % second["id"], delete=True)

    frontend.json(
        f"branches/{branch_id}/branchsettings",
        params={"scope": "testing"},
        expect={"branchsettings": [first]},
    )

    for name, value in [
        ("integer", 4711),
        ("float", 47.11),
        ("boolean", True),
        ("list", ["string", 4711, False]),
        ("object", {"first": "string", "second": 4711, "third": False}),
    ]:
        frontend.json(
            f"branches/{branch_id}/branchsettings",
            post={"scope": "testing", "name": name, "value": value},
            expect=partial_json(name=name, value=value),
        )
