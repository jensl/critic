def check_user(user, session_type=False):
    frontend.page(
        "dashboard",
        expect={
            "script_user": testing.expect.script_user(user)
        })

    if session_type is False:
        if user.id is None:
            # Anonymous user.
            session_type = None
        else:
            session_type = "normal"

    frontend.json(
        "sessions/current",
        params={ "fields": "user,type" },
        expect={
            "user": user.id,
            "type": session_type
        })

anonymous = testing.User.anonymous()
alice = instance.user("alice")
admin = instance.user("admin")

check_user(anonymous)
