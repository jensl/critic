# @dependency 001-install.py
# @users alice

with frontend.signin("alice"):
    settings = frontend.json("usersettings", expect={"usersettings": []})

    first = frontend.json(
        "usersettings",
        post={"scope": "testing", "name": "first", "value": "first value"},
        expect={
            "id": int,
            "user": instance.userid("alice"),
            "scope": "testing",
            "name": "first",
            "value": "first value",
        },
    )

    first = frontend.json(
        "usersettings/%d" % first["id"],
        put={"value": "first value (edited)"},
        expect={
            "id": first["id"],
            "user": instance.userid("alice"),
            "scope": "testing",
            "name": "first",
            "value": "first value (edited)",
        },
    )

    frontend.json(
        "usersettings",
        post={"scope": "testing", "name": "first", "value": 4711},
        expected_http_status=400,
        expect={
            "error": partial_json(message="User setting already defined: testing:first")
        },
    )

    second = frontend.json(
        "usersettings",
        params={"scope": "testing", "name": "second"},
        put={"value": 4711},
        expected_http_status=404,
        expect={
            "error": partial_json(message="User setting not defined: testing:second")
        },
    )

    second = frontend.json(
        "usersettings",
        post={"scope": "testing", "name": "second", "value": "second value"},
        expect={
            "id": int,
            "user": instance.userid("alice"),
            "scope": "testing",
            "name": "second",
            "value": "second value",
        },
    )

    second = frontend.json(
        "usersettings",
        params={"scope": "testing", "name": "second"},
        put={"value": "second value (edited)"},
        expect={
            "id": second["id"],
            "user": instance.userid("alice"),
            "scope": "testing",
            "name": "second",
            "value": "second value (edited)",
        },
    )

    frontend.json(
        "usersettings",
        params={"scope": "testing"},
        expect={"usersettings": [first, second]},
    )

    frontend.json("usersettings/%d" % second["id"], delete=True)

    frontend.json(
        "usersettings", params={"scope": "testing"}, expect={"usersettings": [first]}
    )

    for name, value in [
        ("integer", 4711),
        ("float", 47.11),
        ("boolean", True),
        ("list", ["string", 4711, False]),
        ("object", {"first": "string", "second": 4711, "third": False}),
    ]:
        frontend.json(
            "usersettings",
            post={"scope": "testing", "name": name, "value": value},
            expect=partial_json(name=name, value=value),
        )
