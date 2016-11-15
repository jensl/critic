# Create user 'iris' with no password.

instance.criticctl(["adduser",
                    "--name", "iris",
                    "--email", "iris@example.org",
                    "--fullname", "'Iris von Testing'",
                    "--no-password"])

instance.registeruser("iris")

with_class = testing.expect.with_class

def check_password_ui(expected_value, expected_action):
    def check(document):
        row = document.find("tr", attrs=with_class("password"))
        cell = row.find("td", attrs=with_class("value"))
        button = cell.find("button")

        testing.expect.check(expected_value, cell.contents[0])
        testing.expect.check(
            expected_action, button.string if button else "(no action)")
    return check

with frontend.signin("alice"):
    frontend.page(
        "home",
        params={ "user": "iris" },
        expect={ "password UI": check_password_ui("not set", "(no action)") })

with frontend.signin():
    frontend.page(
        "home",
        params={ "user": "iris",
                 "readonly": "no" },
        expect={ "password UI": check_password_ui("not set", "Set password") })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "new_pw": "testing" })

    frontend.page(
        "home",
        params={ "user": "iris",
                 "readonly": "no" },
        expect={ "password UI": check_password_ui("****", "Set password") })

with frontend.signin("alice"):
    frontend.page(
        "home",
        params={ "user": "iris" },
        expect={ "password UI": check_password_ui("****", "(no action)") })

with frontend.signin("iris"):
    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

    frontend.operation(
        "changepassword",
        data={ "subject": "alice",
               "new_pw": "custom" },
        expect={ "status": "failure",
                 "code": "notallowed" })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "new_pw": "custom" },
        expect={ "status": "failure",
                 "message": "The provided current password is not correct." })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "current_pw": "wrong",
               "new_pw": "custom" },
        expect={ "status": "failure",
                 "message": "The provided current password is not correct." })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "current_pw": "testing",
               "new_pw": "custom" })

    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

with frontend.signin("iris", "custom"):
    instance.criticctl(["passwd",
                        "--name", "iris", "--no-password"])

    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("not set", "Set password") })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "current_pw": "wrong",
               "new_pw": "testing" },
        expect={ "status": "failure",
                 "message": "The provided current password is not correct." })

    frontend.operation(
        "changepassword",
        data={ "subject": "iris",
               "new_pw": "testing" })

    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

instance.criticctl(["passwd",
                    "--name", "iris", "--password", "other"])

with frontend.signin("iris", "other"):
    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

# Try changing admin's password too.

with frontend.signin():
    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

    frontend.operation(
        "changepassword",
        data={ "new_pw": "custom" },
        expect={ "status": "failure",
                 "message": "The provided current password is not correct." })

    frontend.operation(
        "changepassword",
        data={ "current_pw": "wrong",
               "new_pw": "custom" },
        expect={ "status": "failure",
                 "message": "The provided current password is not correct." })

    frontend.operation(
        "changepassword",
        data={ "current_pw": "testing",
               "new_pw": "custom" })

    frontend.page(
        "home",
        expect={ "password UI": check_password_ui("****", "Change password") })

    # Better change it back again, or we'd break lots of following tests...

    frontend.operation(
        "changepassword",
        data={ "current_pw": "custom",
               "new_pw": "testing" })
