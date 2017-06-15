# Create an access token, and restrict it to not allow loading /home.
with frontend.signin("alice"):
    access_token = frontend.json(
        "users/me/accesstokens",
        post={ "title": "token #1 for 006-accesscontrol-http.py" },
        expect={
            "profile": {
                "http": {
                    "rule": "allow",
                    "exceptions": []
                },
                "repositories": {
                    "rule": "allow",
                    "exceptions": []
                },
                "extensions": {
                    "rule": "allow",
                    "exceptions": []
                }
            },
            # use lenient checking
            "*": "*"
        })

    frontend.json(
        "users/me/accesstokens/%d/profile/http" % access_token["id"],
        put={
            "exceptions": [
                {
                    "path_pattern": "home"
                }
            ]
        },
        expect={
            "profile/http": {
                "rule": "allow",
                "exceptions": [
                    {
                        "id": int,
                        "request_method": None,
                        "path_pattern": "home"
                    }
                ]
            }
        })

    # Just to make sure: check that Alice can (still) access /home when
    # authenticating normally.
    frontend.page("home")

with frontend.signin(access_token=access_token):
    # /home should now return "403 Forbidden".
    frontend.page(
        "home",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: GET /home")
        })

    # A POST request should also return "403 Forbidden" (even though it wouldn't
    # have worked anyway.)
    frontend.page(
        "home",
        post="",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: POST /home")
        })

    # /dashboard should still work, of course.
    frontend.page(
        "dashboard",
        expect={
            "document_title": testing.expect.document_title(u"Dashboard"),
            "script_user": testing.expect.script_user(instance.user("alice"))
        })

# Update the access token to deny all requests except "GET /home" instead.
with frontend.signin("alice"):
    result = frontend.json(
        "users/me/accesstokens/%d/profile" % access_token["id"],
        put={
            "http": {
                "rule": "deny",
                "exceptions": [
                    {
                        "request_method": "GET",
                        "path_pattern": "home"
                    }
                ]
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
                            "path_pattern": "home"
                        }
                    ]
                },
                "repositories": {
                    "rule": "allow",
                    "exceptions": []
                },
                "extensions": {
                    "rule": "allow",
                    "exceptions": []
                }
            }
        })

    home_exception = result["profile"]["http"]["exceptions"][0]

with frontend.signin(access_token=access_token):
    # /home should now be allowed.
    frontend.page(
        "home",
        expect={
            "document_title": testing.expect.document_title(u"Alice von Testing's Home"),
            "script_user": testing.expect.script_user(instance.user("alice"))
        })

    # A POST request should still return "403 Forbidden" though.
    frontend.page(
        "home",
        post="",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: POST /home")
        })

    # /dashboard should no longer work.
    frontend.page(
        "dashboard",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: GET /dashboard")
        })

# Update the access token to also allow access to "GET /dashboard".
with frontend.signin("alice"):
    frontend.json(
        "users/me/accesstokens/%d/profile/http/exceptions" % access_token["id"],
        post={
            "request_method": "GET",
            "path_pattern": "dashboard"
        },
        expect={
            "profile/http/exceptions": [
                {
                    "id": int,
                    "request_method": "GET",
                    "path_pattern": "home"
                },
                {
                    "id": int,
                    "request_method": "GET",
                    "path_pattern": "dashboard"
                }
            ]
        })

with frontend.signin(access_token=access_token):
    # /dashboard should now work again.
    frontend.page(
        "dashboard",
        expect={
            "document_title": testing.expect.document_title(u"Dashboard"),
            "script_user": testing.expect.script_user(instance.user("alice"))
        })

# Update the access token by deleting the /home exception.
with frontend.signin("alice"):
    frontend.json(
        ("users/me/accesstokens/%d/profile/http/exceptions/%d"
         % (access_token["id"], home_exception["id"])),
        delete=True,
        expect={
            "profile": {
                "http": {
                    "rule": "deny",
                    "exceptions": [
                        {
                            "id": int,
                            "request_method": "GET",
                            "path_pattern": "dashboard"
                        }
                    ]
                },
                "repositories": {
                    "rule": "allow",
                    "exceptions": []
                },
                "extensions": {
                    "rule": "allow",
                    "exceptions": []
                }
            },
            # use lenient checking
            "*": "*"
        })

with frontend.signin(access_token=access_token):
    # /home should now return "403 Forbidden" again.
    frontend.page(
        "home",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: GET /home")
        })

    # /dashboard should still work.
    frontend.page(
        "dashboard",
        expect={
            "document_title": testing.expect.document_title(u"Dashboard"),
            "script_user": testing.expect.script_user(instance.user("alice"))
        })

# Create an access token for anonymous access, and restrict it to not allow
# loading /branches.
with frontend.signin():
    access_token = frontend.json(
        "accesstokens",
        post={
            "title": "token #2 for 006-accesscontrol-http.py",
            "access_type": "anonymous",
            "profile": {
                "http": {
                    "rule": "allow",
                    "exceptions": [{
                        "path_pattern": "branches"
                    }]
                }
            },
        })

with frontend.signin(access_token=access_token):
    check_user(anonymous, "accesstoken")

    # /branches should now return "403 Forbidden".
    frontend.page(
        "branches",
        expected_http_status=403,
        expect={
            "message_title": testing.expect.message(
                u"Access denied",
                u"Access denied: GET /branches")
        })
