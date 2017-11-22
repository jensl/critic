# @dependency 001-install.py
# @dependency 004-repositories/003-small.py
# @users alice

repository_id = instance.repository("small").id

with frontend.signin():
    settings = frontend.json("repositorysettings", expect={"repositorysettings": []})

    first = frontend.json(
        "repositorysettings",
        post={
            "repository": "small",
            "scope": "testing",
            "name": "first",
            "value": "first value",
        },
        expect={
            "id": int,
            "repository": repository_id,
            "scope": "testing",
            "name": "first",
            "value": "first value",
        },
    )

    first = frontend.json(
        "repositorysettings/%d" % first["id"],
        put={"value": "first value (edited)"},
        expect={
            "id": first["id"],
            "repository": repository_id,
            "scope": "testing",
            "name": "first",
            "value": "first value (edited)",
        },
    )

    frontend.json(
        "repositorysettings",
        post={
            "repository": "small",
            "scope": "testing",
            "name": "first",
            "value": 4711,
        },
        expected_http_status=400,
        expect={
            "error": partial_json(
                message="Repository setting already defined: testing:first"
            )
        },
    )

    second = frontend.json(
        f"repositories/{repository_id}/repositorysettings",
        params={"scope": "testing", "name": "second"},
        put={"value": 4711},
        expected_http_status=404,
        expect={
            "error": partial_json(
                message="Repository setting not defined: testing:second"
            )
        },
    )

    second = frontend.json(
        f"repositories/{repository_id}/repositorysettings",
        post={"scope": "testing", "name": "second", "value": "second value"},
        expect={
            "id": int,
            "repository": repository_id,
            "scope": "testing",
            "name": "second",
            "value": "second value",
        },
    )

    second = frontend.json(
        f"repositories/{repository_id}/repositorysettings",
        params={"scope": "testing", "name": "second"},
        put={"value": "second value (edited)"},
        expect={
            "id": second["id"],
            "repository": repository_id,
            "scope": "testing",
            "name": "second",
            "value": "second value (edited)",
        },
    )

    frontend.json(
        f"repositories/{repository_id}/repositorysettings",
        params={"scope": "testing"},
        expect={"repositorysettings": [first, second]},
    )

    frontend.json("repositorysettings/%d" % second["id"], delete=True)

    frontend.json(
        f"repositories/{repository_id}/repositorysettings",
        params={"scope": "testing"},
        expect={"repositorysettings": [first]},
    )

    for name, value in [
        ("integer", 4711),
        ("float", 47.11),
        ("boolean", True),
        ("list", ["string", 4711, False]),
        ("object", {"first": "string", "second": 4711, "third": False}),
    ]:
        frontend.json(
            f"repositories/{repository_id}/repositorysettings",
            post={"scope": "testing", "name": name, "value": value},
            expect=partial_json(name=name, value=value),
        )
