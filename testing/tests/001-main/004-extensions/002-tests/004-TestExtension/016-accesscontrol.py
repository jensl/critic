# Create an access token, and restrict it to not allow execution of
# Alice's TestExtension.
with frontend.signin("alice"):
    access_token = frontend.json(
        "users/me/accesstokens",
        post={ "title": "token for 016-accesscontrol.py" })

    extension = frontend.json(
        "extensions",
        params={ "key": "alice/TestExtension" })

    frontend.json(
        ("users/me/accesstokens/%d/profile/extensions/exceptions"
         % access_token["id"]),
        post={ "access_type": "execute",
               "extension": "alice/TestExtension" },
        expect={
            "profile/extensions/exceptions": [{
                "id": int,
                "access_type": "execute",
                "extension": extension["id"]
            }]
        })

with frontend.signin(access_token=access_token):
    # Trying to execute an extension role should give a "403 Forbidden".
    frontend.page(
        "echo",
        expected_http_status=403)
