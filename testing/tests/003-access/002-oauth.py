# @user alice

import json
import re
import urllib
import urllib.parse


def signout():
    frontend.json("sessions/current", delete=True, expected_http_status=204)


def isprefix(expected, actual):
    return actual.startswith(expected)


def issuffix(expected, actual):
    return actual.endswith(expected)


def start_externalauth(name, target_url="/"):
    response = frontend.request(
        f"api/externalauth/{name}/start", params={"target": target_url}
    )

    testing.expect.check(302, response.status_code)

    redirect_url = response.headers["Location"]

    testing.expect.check("https://example.com/authorize?", redirect_url, equal=isprefix)

    parsed_url = urllib.parse.urlparse(redirect_url)
    parsed_query = urllib.parse.parse_qs(parsed_url.query)
    state = parsed_query.get("state", ["no state received"])[0]

    if state == "no state received":
        testing.expect.check(
            "<state parameter in authorize URI query>",
            "<no state parameter: %r>" % parsed_url.query,
        )

    return state


def finish_externalauth(name, state):
    frontend.collect_session_cookie()

    response = frontend.request(
        "api/externalauth/%s/finish" % name, params={"state": state, "code": "correct"}
    )

    testing.expect.check(302, response.status_code)

    return response.headers["Location"]


# Configure our custom external providers.

settings = []


def setting(key, value):
    return {"key": key, "description": "N/A", "value": value}


def dummy_provider(
    name, allow_user_registration, verify_email_addresses, bypass_createuser
):
    prefix = f"authentication.external_providers.{name}"
    return [
        setting(f"{prefix}.enabled", True),
        setting(f"{prefix}.allow_user_registration", allow_user_registration),
        setting(f"{prefix}.bypass_createuser", bypass_createuser),
        setting(f"{prefix}.client_id", "DummyClientId"),
        setting(f"{prefix}.client_secret", "DummyClientSecret"),
        setting(f"{prefix}.verify_email_address", verify_email_addresses),
    ]


settings.extend(dummy_provider("alice", False, False, False))
settings.extend(dummy_provider("carol", True, False, False))
settings.extend(dummy_provider("felix", True, False, True))
settings.extend(dummy_provider("gina", True, True, False))

instance.criticctl(["settings", "create"], stdin_data=json.dumps(settings))
instance.restart()

# Check that all the expected links to external providers are present
# on the "Sign in" page.

NAMES = ["alice", "carol", "felix", "gina"]


def provider_json(name):
    return {
        "identifier": name,
        "title": name.capitalize() + " account",
        "account_id_label": name.capitalize() + " username",
    }


frontend.json(
    "sessions/current",
    expect=partial_json(
        {
            "providers": [
                provider_json("alice"),
                provider_json("carol"),
                provider_json("felix"),
                provider_json("gina"),
            ]
        }
    ),
)

#
# Try to sign in using the 'alice' provider, then connect alice's
# account manually, and try again.  Make some mistakes along the way.
#

state = start_externalauth("alice")

# Try with the wrong state.
response = frontend.request(
    "api/externalauth/alice/finish",
    params={"state": "not the right state", "code": "irrelevant"},
)
testing.expect.check(400, response.status_code)


# Try with the wrong code (the right code is always "correct".)
response = frontend.request(
    "api/externalauth/alice/finish", params={"state": state, "code": "incorrect"}
)
testing.expect.check(400, response.status_code)

redirect_url = finish_externalauth("alice", state)

# Connect the account manually.
instance.criticctl(
    [
        "connect",
        "--username",
        "alice",
        "--provider",
        "alice",
        "--account",
        "account-alice",
    ]
)

# Sign in for real now.
state = start_externalauth("alice", target_url="/r/12345")
redirect_url = finish_externalauth("alice", state)

testing.expect.check("/r/12345", redirect_url)

with frontend.cookie_session(signout):
    frontend.json(
        "sessions/current", expect=partial_json({"user": instance.userid("alice")})
    )

#
# Create user 'carol' by signing in using the 'carol' provider.
#

state = start_externalauth("carol")
redirect_url = finish_externalauth("carol", state)

testing.expect.check("/", redirect_url)

with frontend.cookie_session(signout):
    result = frontend.json(
        "sessions/current",
        params={"include": "externalaccounts"},
        expect=partial_json(
            {
                "user": None,
                "external_account": int,
                "linked": {
                    "externalaccounts": [
                        {
                            "id": int,
                            "provider": {
                                "identifier": "carol",
                                "title": "Carol account",
                            },
                            "account": {
                                "id": "account-carol",
                                "url": "https://example.com/user/account-carol",
                                "username": "carol",
                                "fullname": "Carol von Testing",
                                "email": "carol@example.org",
                            },
                            "user": None,
                        }
                    ]
                },
            }
        ),
    )

    external_account = result["linked"]["externalaccounts"][0]

    carol = instance.registeruser("carol")

    frontend.json(
        "users",
        post={
            "name": "carol",
            "fullname": "Carol von Testing",
            "email": "carol@example.org",
        },
        expect={
            "id": carol.id,
            "name": "carol",
            "fullname": "Carol von Testing",
            "status": "current",
            "email": "carol@example.org",
        },
    )

    frontend.json(
        "sessions/current",
        expect=partial_json(
            {"user": carol.id, "external_account": external_account["id"]}
        ),
    )

#
# Create user 'felix' by signin in using the 'felix' provider, which
# has 'bypass_createuser' set, so this will be quick.
#

state = start_externalauth("felix")
redirect_url = finish_externalauth("felix", state)

testing.expect.check("/", redirect_url)

felix = instance.registeruser("felix")

with frontend.cookie_session(signout):
    frontend.json(
        "sessions/current",
        params={"include": "externalaccounts"},
        expect=partial_json(
            {
                "user": felix.id,
                "external_account": int,
                "linked": {
                    "externalaccounts": [
                        {
                            "id": int,
                            "provider": {
                                "identifier": "felix",
                                "title": "Felix account",
                            },
                            "account": {
                                "id": "account-felix",
                                "url": "https://example.com/user/account-felix",
                                "username": "felix",
                                "fullname": "Felix von Testing",
                                "email": "felix@example.org",
                            },
                            "user": felix.id,
                        }
                    ]
                },
            }
        ),
    )

    frontend.json(
        "users/me/useremails",
        expect={
            "useremails": [
                {
                    "id": int,
                    "user": felix.id,
                    "address": "felix@example.org",
                    "is_selected": True,
                    "status": "trusted",
                }
            ]
        },
    )

#
# Create user 'gina' by signin in using the 'gina' provider, which
# has 'verify_email_addresses' set.
#

state = start_externalauth("gina")
redirect_url = finish_externalauth("gina", state)

testing.expect.check("/", redirect_url)

gina = instance.registeruser("gina")

with frontend.cookie_session(signout):
    frontend.json(
        "users",
        post={
            "name": "gina",
            "fullname": "Gina von Testing",
            "email": "gina@example.org",
        },
        expect={
            "id": gina.id,
            "name": "gina",
            "fullname": "Gina von Testing",
            "status": "current",
            "email": None,
        },
    )

    frontend.json(
        "sessions/current",
        params={"include": "externalaccounts,users"},
        expect=partial_json(
            {
                "user": gina.id,
                "external_account": int,
                "linked": {
                    "externalaccounts": [
                        {
                            "id": int,
                            "provider": {"identifier": "gina", "title": "Gina account"},
                            "account": {
                                "id": "account-gina",
                                "url": "https://example.com/user/account-gina",
                                "username": "gina",
                                "fullname": "Gina von Testing",
                                "email": "gina@example.org",
                            },
                            "user": gina.id,
                        }
                    ],
                    "users": [
                        {
                            "id": gina.id,
                            "name": "gina",
                            "fullname": "Gina von Testing",
                            "email": None,
                        }
                    ],
                },
            }
        ),
    )

    frontend.json(
        "users/me/useremails",
        expect={
            "useremails": [
                {
                    "id": int,
                    "user": gina.id,
                    "address": "gina@example.org",
                    "is_selected": True,
                    "status": "unverified",
                }
            ]
        },
    )

    # expect_system_mail("wsgi[registeruser]: User 'gina' registered")

    # subject = r"\[Critic\] Please verify your email: gina@example\.org"

    # mailbox.pop(accept=[testing.mailbox.ToRecipient("gina@example.org"),
    #                     testing.mailbox.WithSubject(subject)])
