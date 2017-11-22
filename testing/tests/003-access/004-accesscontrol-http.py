# @user alice

# Create an access token, and restrict it to not allow loading /api/v1/branches.
with frontend.signin("alice"):
    access_token = frontend.json(
        "users/me/accesstokens",
        post={"title": "token #1 for 006-accesscontrol-http.py"},
        expect={
            "profile": {
                "http": {"rule": "allow", "exceptions": []},
                "repositories": {"rule": "allow", "exceptions": []},
                "extensions": {"rule": "allow", "exceptions": []},
            },
            # use lenient checking
            "*": "*",
        },
    )

    frontend.json(
        "users/me/accesstokens/%d/profile/http" % access_token["id"],
        put={"exceptions": [{"path_pattern": "api/v1/branches"}]},
        expect={
            "profile/http": {
                "rule": "allow",
                "exceptions": [
                    {
                        "id": int,
                        "request_method": None,
                        "path_pattern": "api/v1/branches",
                    }
                ],
            }
        },
    )

    # Just to make sure: check that Alice can (still) access /api/v1/branches
    # when authenticating normally.
    frontend.json("branches")

with frontend.signin(access_token=access_token):
    # /api/v1/branches should now return "403 Forbidden".
    frontend.json(
        "branches", expect_access_denied="Access denied: GET /api/v1/branches"
    )

    # A POST request should also return "403 Forbidden" (even though it wouldn't
    # have worked anyway.)
    frontend.json(
        "branches", post={}, expect_access_denied="Access denied: POST /api/v1/branches"
    )

    # /api/v1/repositories should still work, of course.
    frontend.json("repositories", expect={"repositories": list})

# Update the access token to deny all requests except "GET /api/v1/branches"
# instead.
with frontend.signin("alice"):
    result = frontend.json(
        "users/me/accesstokens/%d/profile" % access_token["id"],
        put={
            "http": {
                "rule": "deny",
                "exceptions": [
                    {"request_method": "GET", "path_pattern": "api/v1/branches"}
                ],
            }
        },
        expect={
            "profile": {
                "http": {
                    "rule": "deny",
                    "exceptions": [
                        {
                            "id": int,
                            "request_method": "GET",
                            "path_pattern": "api/v1/branches",
                        }
                    ],
                },
                "repositories": {"rule": "allow", "exceptions": []},
                "extensions": {"rule": "allow", "exceptions": []},
            }
        },
    )

    branches_exception = result["profile"]["http"]["exceptions"][0]

with frontend.signin(access_token=access_token):
    # /api/v1/branches should now be allowed.
    frontend.json("branches", expect={"branches": list})

    # A POST request should still return "403 Forbidden" though.
    frontend.json(
        "branches", post={}, expect_access_denied="Access denied: POST /api/v1/branches"
    )

    # /api/v1/repositories should no longer work.
    frontend.json(
        "repositories", expect_access_denied="Access denied: GET /api/v1/repositories"
    )

# Update the access token to also allow access to "GET /api/v1/repositories".
with frontend.signin("alice"):
    frontend.json(
        "users/me/accesstokens/%d/profile/http/exceptions" % access_token["id"],
        post={"request_method": "GET", "path_pattern": "api/v1/repositories"},
        expect={
            "profile/http/exceptions": [
                {"id": int, "request_method": "GET", "path_pattern": "api/v1/branches"},
                {
                    "id": int,
                    "request_method": "GET",
                    "path_pattern": "api/v1/repositories",
                },
            ]
        },
    )

with frontend.signin(access_token=access_token):
    # /api/v1/repositories should now work again.
    frontend.json("repositories", expect={"repositories": list})

# Update the access token by deleting the /api/v1/branches exception.
with frontend.signin("alice"):
    frontend.json(
        (
            "users/me/accesstokens/%d/profile/http/exceptions/%d"
            % (access_token["id"], branches_exception["id"])
        ),
        delete=True,
        expected_http_status=200,
        expect={
            "profile": {
                "http": {
                    "rule": "deny",
                    "exceptions": [
                        {
                            "id": int,
                            "request_method": "GET",
                            "path_pattern": "api/v1/repositories",
                        }
                    ],
                },
                "repositories": {"rule": "allow", "exceptions": []},
                "extensions": {"rule": "allow", "exceptions": []},
            },
            # use lenient checking
            "*": "*",
        },
    )

with frontend.signin(access_token=access_token):
    # /api/v1/branches should now return "403 Forbidden" again.
    frontend.json(
        "branches", expect_access_denied="Access denied: GET /api/v1/branches"
    )

    # /api/v1/repositories should still work.
    frontend.json("repositories", expect={"repositories": list})

# Create an access token for anonymous access, and restrict it to not allow
# loading /api/v1/users.
with frontend.signin():
    access_token = frontend.json(
        "accesstokens",
        post={
            "title": "token #2 for 006-accesscontrol-http.py",
            "access_type": "anonymous",
            "profile": {
                "http": {
                    "rule": "allow",
                    "exceptions": [{"path_pattern": "api/v1/users"}],
                }
            },
        },
    )

with frontend.signin(access_token=access_token):
    check_user(anonymous, "accesstoken")

    # /branches should now return "403 Forbidden".
    frontend.json("users", expect_access_denied="Access denied: GET /api/v1/users")
