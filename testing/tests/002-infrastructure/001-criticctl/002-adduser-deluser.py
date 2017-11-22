# @user alice

# Scenario: Try to add a user 'alice' (already exists).
try:
    instance.criticctl(
        [
            "adduser",
            "--username",
            "alice",
            "--fullname",
            "Alice von Testing",
            "--email",
            "alice@example.org",
            "--password",
            "testing",
        ]
    )
except testing.CriticctlError as error:
    if "alice: user already exists" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stdout
        )
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Try to delete the user 'nosuchuser' (no such user).
try:
    instance.criticctl(["deluser", "--username", "nosuchuser", "--retire"])
except testing.CriticctlError as error:
    if "nosuchuser: no such user" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stdout
        )
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Add a user 'extra' and then retire, re-enable, and finally disable
#           that account.
try:
    instance.criticctl(
        [
            "adduser",
            "--username",
            "extra",
            "--fullname",
            "Extra von Testing",
            "--email",
            "extra@example.org",
            "--password",
            "testing",
        ]
    )
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    instance.registeruser("extra")

    extra_id = frontend.json(
        "users?name=extra",
        expect={
            "id": int,
            "name": "extra",
            "fullname": "Extra von Testing",
            "status": "current",
            "email": "extra@example.org",
        },
    )["id"]

    try:
        instance.criticctl(["deluser", "--username", "extra", "--retire"])
    except testing.CriticctlError as error:
        logger.error("correct criticctl usage failed:\n%s" % error.stdout)

    with frontend.signin():
        frontend.json(
            f"users/{extra_id}",
            expect={
                "id": int,
                "name": "extra",
                "fullname": "Extra von Testing",
                "status": "retired",
                "email": "extra@example.org",
                "roles": [],
                "password_status": "set",
            },
        )

    with frontend.signin("extra"):
        frontend.json(
            "users/me",
            expect={
                "id": extra_id,
                "name": "extra",
                "fullname": "Extra von Testing",
                "status": "current",
                "email": "extra@example.org",
                "roles": [],
                "password_status": "set",
            },
        )

    try:
        instance.criticctl(["deluser", "--username", "extra", "--disable"])
    except testing.CriticctlError as error:
        logger.error("correct criticctl usage failed:\n%s" % error.stdout)

    with frontend.signin():
        frontend.json(
            f"users/{extra_id}",
            expect={
                "id": extra_id,
                "name": "__disabled_%d__" % extra_id,
                "fullname": "(disabled account)",
                "status": "disabled",
                "email": None,
                "roles": [],
                "password_status": "disabled",
            },
        )

    instance.renameuser("extra", "__disabled_7__")
