# @flag disabled

# Create user 'iris' with no password.

instance.criticctl(
    [
        "adduser",
        "--username",
        "iris",
        "--fullname",
        "'Iris von Testing'",
        "--email",
        "iris@example.org",
        "--no-password",
    ]
)

instance.registeruser("iris")

with frontend.signin():
    frontend.page(
        "home",
        params={"user": "iris", "readonly": "no"},
        expect={"password UI": check_password_ui("not set", "Set password")},
    )

    frontend.operation("changepassword", data={"subject": "iris", "new_pw": "testing"})

    frontend.page(
        "home",
        params={"user": "iris", "readonly": "no"},
        expect={"password UI": check_password_ui("****", "Set password")},
    )

with frontend.signin("alice"):
    frontend.page(
        "home",
        params={"user": "iris"},
        expect={"password UI": check_password_ui("****", "(no action)")},
    )

with frontend.signin("iris"):
    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

    frontend.operation(
        "changepassword",
        data={"subject": "alice", "new_pw": "custom"},
        expect={"status": "failure", "code": "notallowed"},
    )

    frontend.operation(
        "changepassword",
        data={"subject": "iris", "new_pw": "custom"},
        expect={
            "status": "failure",
            "message": "The provided current password is not correct.",
        },
    )

    frontend.operation(
        "changepassword",
        data={"subject": "iris", "current_pw": "wrong", "new_pw": "custom"},
        expect={
            "status": "failure",
            "message": "The provided current password is not correct.",
        },
    )

    frontend.operation(
        "changepassword",
        data={"subject": "iris", "current_pw": "testing", "new_pw": "custom"},
    )

    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

with frontend.signin("iris", "custom"):
    instance.criticctl(["passwd", "--username", "iris", "--no-password"])

    frontend.page(
        "home", expect={"password UI": check_password_ui("not set", "Set password")}
    )

    frontend.operation(
        "changepassword",
        data={"subject": "iris", "current_pw": "wrong", "new_pw": "testing"},
        expect={
            "status": "failure",
            "message": "The provided current password is not correct.",
        },
    )

    frontend.operation("changepassword", data={"subject": "iris", "new_pw": "testing"})

    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

instance.criticctl(["passwd", "--username", "iris", "--password", "other"])

with frontend.signin("iris", "other"):
    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

# Try changing admin's password too.

with frontend.signin():
    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

    frontend.operation(
        "changepassword",
        data={"new_pw": "custom"},
        expect={
            "status": "failure",
            "message": "The provided current password is not correct.",
        },
    )

    frontend.operation(
        "changepassword",
        data={"current_pw": "wrong", "new_pw": "custom"},
        expect={
            "status": "failure",
            "message": "The provided current password is not correct.",
        },
    )

    frontend.operation(
        "changepassword", data={"current_pw": "testing", "new_pw": "custom"}
    )

    frontend.page(
        "home", expect={"password UI": check_password_ui("****", "Change password")}
    )

    # Better change it back again, or we'd break lots of following tests...

    frontend.operation(
        "changepassword", data={"current_pw": "custom", "new_pw": "testing"}
    )
