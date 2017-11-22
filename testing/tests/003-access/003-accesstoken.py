# @users alice, bob

empty_profile = {
    "id": int,
    "title": None,
    "http": {"rule": "allow", "exceptions": []},
    "repositories": {"rule": "allow", "exceptions": []},
    "extensions": {"rule": "allow", "exceptions": []},
}

# Sign in and create an access token.
with frontend.signin("alice"):
    check_user(alice)

    access_token = frontend.json(
        "users/%d/accesstokens" % alice.id,
        post={"title": "005-accesstoken"},
        expect={
            "id": int,
            "access_type": "user",
            "user": alice.id,
            "title": "005-accesstoken",
            "token": str,
            "profile": int,
        },
    )

    token_id = access_token["id"]
    token = access_token.pop("token")

    # Get the access token and its components.
    frontend.json("accesstokens/%d" % token_id, expect=access_token)
    frontend.json("users/me/accesstokens/%d" % token_id, expect=access_token)
    frontend.json("accesstokens/%d/profile" % token_id, expect=empty_profile)

check_user(anonymous)

# Check that Alice can't authenticate using the token via the regular login
# mechanism.
frontend.json(
    "sessions",
    post={"username": "alice", "password": token},
    expected_http_status=403,
    expect=expected_error(title="Session error", message="Wrong password"),
)

check_user(anonymous)

# Check that Alice can authenticate with the token using HTTP basic authentication (using
# the token as password).
with frontend.signin(username="alice", password=token, use_httpauth=True):
    check_user(alice, "accesstoken")

# Check that Alice can authenticate using the token using HTTP bearer authentication.
with frontend.signin(token=token):
    check_user(alice, "accesstoken")

check_user(anonymous)

# Check that Bob can't access Alice's access tokens.
with frontend.signin("bob"):
    frontend.json(
        "sessions/current", expect=partial_json({"user": instance.userid("bob")})
    )

    frontend.json("users/%d/accesstokens" % alice.id, expected_http_status=403)
    frontend.json(
        "users/%d/accesstokens/%d" % (alice.id, token_id), expected_http_status=403
    )
    frontend.json("accesstokens", expected_http_status=403)
    frontend.json("accesstokens/%d" % token_id, expected_http_status=403)

# Check that an administrator can access Alice's access tokens.
with frontend.signin():
    frontend.json(
        "users/%d/accesstokens" % alice.id, expect={"accesstokens": [access_token]}
    )
    frontend.json(
        "users/%d/accesstokens/%d" % (alice.id, token_id), expect=access_token
    )
    frontend.json("accesstokens", expect={"accesstokens": [access_token]})
    frontend.json("accesstokens/%d" % token_id, expect=access_token)

check_user(anonymous)

# Sign in and delete the access token.
with frontend.signin("alice"):
    check_user(alice)

    frontend.json(
        "users/%d/accesstokens/%d" % (alice.id, token_id),
        delete=True,
        expected_http_status=204,
    )

check_user(anonymous)

# Check that Alice can no longer authenticate using the token and HTTP
# authentication.
with frontend.signin(token=token):
    # Using invalid HTTP authentication should trigger a 401 Unauthorized (and
    # not lead to anonymous access.)
    response = frontend.request("users/me")
    testing.expect.check(401, response.status_code)

check_user(anonymous)

# Sign in as admin and create an access token for anonymous access.
with frontend.signin():
    check_user(admin)

    access_token = frontend.json(
        "accesstokens",
        post={"access_type": "anonymous", "title": "005-accesstoken (anonymous)"},
        expect={
            "id": int,
            "access_type": "anonymous",
            "user": None,
            "title": "005-accesstoken (anonymous)",
            "token": str,
            "profile": int,
        },
    )

    token_id = access_token["id"]
    token = access_token.pop("token")

check_user(anonymous)

# Check that we can authenticate using the token and HTTP authentication, and
# that we're then anonymous.
#
# This is somewhat silly; we were anonymous before, so it's difficult to know if
# authentication succeeded or not.  This kind of access token is mostly useful
# in a system that doesn't otherwise allow anonymous access.
with frontend.signin(token=token):
    check_user(anonymous, "accesstoken")

check_user(anonymous)

# Sign in and delete the access token.
with frontend.signin():
    check_user(admin)

    frontend.json("accesstokens/%d" % token_id, delete=True, expected_http_status=204)

# Check that Alice (not an administrator) can't create an anonymous token.
with frontend.signin("alice"):
    check_user(alice)

    access_token = frontend.json(
        "accesstokens",
        post={"access_type": "anonymous"},
        expected_http_status=403,
        expect=expected_error(
            title="Permission denied", message="Must be an administrator"
        ),
    )
