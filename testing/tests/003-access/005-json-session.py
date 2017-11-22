# @dependency 003-access/002-oauth.py


def test_provider(name):
    return {
        "identifier": name,
        "title": f"{name.capitalize()} account",
        "account_id_label": f"{name.capitalize()} username",
    }


frontend.json(
    "sessions/current",
    expect={
        "user": None,
        "type": None,
        "external_account": None,
        "fields": [
            {
                "identifier": "username",
                "label": "Username",
                "hidden": False,
                "description": None,
            },
            {
                "identifier": "password",
                "label": "Password",
                "hidden": True,
                "description": None,
            },
        ],
        "providers": [
            test_provider("alice"),
            test_provider("carol"),
            test_provider("felix"),
            test_provider("gina"),
        ],
    },
)

# Sign in as alice.
with frontend.signin("alice", cached=False):
    check_user(alice)

    # Sign out prematurely, just to make sure the signout actually works as
    # expected.
    #
    # Exiting the frontend.signin() scope will do the same, but will cause the
    # session cookie to be "deleted" regardless of what the server does, so
    # could hide signout failures.
    frontend.json("sessions/current", delete=True, expected_http_status=204)

    check_user(anonymous)

with testing.utils.access_token("alice", profile={}) as access_token:
    with frontend.signin(access_token=access_token):
        check_user(alice, "accesstoken")

frontend.json(
    "sessions",
    expected_http_status=400,
    expect=expected_error(
        title="Invalid API request",
        message="Resource requires an argument: v1/sessions",
    ),
)

frontend.json(
    "sessions/invalid",
    expected_http_status=400,
    expect=expected_error(
        title="Invalid API request", message='Resource argument must be "current"'
    ),
)

frontend.json(
    "sessions",
    post={"username": "alice", "password": "wrong"},
    expected_http_status=403,
    expect=expected_error(title="Session error", message="Wrong password"),
)

frontend.json(
    "sessions",
    post={"username": "bobsicle", "password": "testing"},
    expected_http_status=403,
    expect=expected_error(title="Session error", message="Invalid username"),
)
