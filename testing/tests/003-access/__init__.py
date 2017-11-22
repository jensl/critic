def check_user(user, session_type=False):
    if session_type is False:
        if user.id is None:
            # Anonymous user.
            session_type = None
        else:
            session_type = "normal"

    frontend.json(
        "sessions/current",
        params={"fields": "user,type"},
        expect={"user": user.id, "type": session_type, "is_partial": True},
    )


anonymous = testing.User.anonymous()
alice = instance.user("alice")
admin = instance.user("admin")

check_user(anonymous)
