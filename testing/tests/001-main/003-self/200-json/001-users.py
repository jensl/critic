# @dependency 001-main/001-empty/003-criticctl/002-adduser-deluser.py
# @dependency 001-main/001-empty/004-mixed/003-oauth.py
# @dependency 001-main/001-empty/004-mixed/004-password.py
# @dependency 001-main/003-self/028-gitemails.py

frontend.json(
    "users",
    expect={ "users": [user_json("admin", "Testing Administrator"),
                       user_json("alice"),
                       user_json("bob"),
                       user_json("dave"),
                       user_json("erin"),
                       user_json("howard"),
                       user_json("extra", status="retired"),
                       user_json("carol"),
                       user_json("felix"),
                       user_json("gina", no_email=True),
                       user_json("iris")] })

frontend.json(
    "users",
    params={ "status": "current" },
    expect={ "users": [user_json("admin", "Testing Administrator"),
                       user_json("alice"),
                       user_json("bob"),
                       user_json("dave"),
                       user_json("erin"),
                       user_json("howard"),
                       user_json("carol"),
                       user_json("felix"),
                       user_json("gina", no_email=True),
                       user_json("iris")] })

frontend.json(
    "users",
    params={ "status": "retired" },
    expect={ "users": [user_json("extra", status="retired")] })

frontend.json(
    "users",
    params={ "sort": "fullname" },
    expect={ "users": [user_json("alice"),
                       user_json("bob"),
                       user_json("carol"),
                       user_json("dave"),
                       user_json("erin"),
                       user_json("extra", status="retired"),
                       user_json("felix"),
                       user_json("gina", no_email=True),
                       user_json("howard"),
                       user_json("iris"),
                       user_json("admin", "Testing Administrator")] })

frontend.json(
    "users",
    params={ "sort": "fullname",
             "count": "4" },
    expect={ "users": [user_json("alice"),
                       user_json("bob"),
                       user_json("carol"),
                       user_json("dave")] })

frontend.json(
    "users",
    params={ "sort": "fullname",
             "offset": "2",
             "count": "4" },
    expect={ "users": [user_json("carol"),
                       user_json("dave"),
                       user_json("erin"),
                       user_json("extra", status="retired")] })

frontend.json(
    "users",
    params={ "sort": "fullname",
             "offset": "6" },
    expect={ "users": [user_json("felix"),
                       user_json("gina", no_email=True),
                       user_json("howard"),
                       user_json("iris"),
                       user_json("admin", "Testing Administrator")] })

frontend.json(
    "users/%d" % instance.userid("alice"),
    expect=user_json("alice"))

frontend.json(
    "users/%d" % instance.userid("alice"),
    params={ "fields": "id" },
    expect={ "id": instance.userid("alice") })

frontend.json(
    "users",
    params={ "name": "alice" },
    expect=user_json("alice"))

frontend.json(
    "users/%d/emails" % instance.userid("alice"),
    expect={ "emails": [{ "address": "alice@example.org",
                          "selected": True,
                          "verified": None }] })

frontend.json(
    "users/%d/emails/1" % instance.userid("alice"),
    expect={ "address": "alice@example.org",
             "selected": True,
             "verified": None })

filter_json = { "id": int,
                "type": "reviewer",
                "path": "028-gitemails/",
                "repository": 1,
                "delegates": [instance.userid("erin")] }

frontend.json(
    "users/%d/filters" % instance.userid("alice"),
    expect={ "filters": [filter_json] })

frontend.json(
    "users/%d/filters" % instance.userid("alice"),
    params={ "repository": "critic" },
    expect={ "filters": [filter_json] })

result = frontend.json(
    "users/%d/filters" % instance.userid("alice"),
    params={ "repository": "1" },
    expect={ "filters": [filter_json] })

frontend.json(
    "users/%d/filters" % instance.userid("alice"),
    params={ "include": "users,repositories" },
    expect={ "filters": [{ "id": int,
                           "type": "reviewer",
                           "path": "028-gitemails/",
                           "repository": 1,
                           "delegates": [instance.userid("erin")] }],
             "linked": { "repositories": [critic_json],
                         "users": [user_json("erin")] }})

frontend.json(
    "users/%d/filters/%d" % (instance.userid("alice"),
                             result["filters"][0]["id"]),
    expect={ "id": result["filters"][0]["id"],
             "type": "reviewer",
             "path": "028-gitemails/",
             "repository": 1,
             "delegates": [instance.userid("erin")] })

# Test asking for just the list of delegates.
frontend.json(
    "users/%d/filters/%d/delegates" % (instance.userid("alice"),
                                       result["filters"][0]["id"]),
    expect={ "delegates": [instance.userid("erin")] })

# Check that the repository is not linked when we ask for just delegates.
frontend.json(
    "users/%d/filters/%d/delegates" % (instance.userid("alice"),
                                       result["filters"][0]["id"]),
    params={ "include": "users,repositories" },
    expect={ "delegates": [instance.userid("erin")],
             "linked": { "repositories": [],
                         "users": [user_json("erin")] }})

frontend.json(
    "users/%d,%d,%d" % (instance.userid("alice"),
                        instance.userid("bob"),
                        instance.userid("dave")),
    expect={ "users": [user_json("alice"),
                       user_json("bob"),
                       user_json("dave")] })

frontend.json(
    "users/%d,%d,%d" % (instance.userid("alice"),
                        instance.userid("bob"),
                        instance.userid("dave")),
    params={ "fields[users]": "name" },
    expect={ "users": [{ "name": "alice" },
                       { "name": "bob" },
                       { "name": "dave" }] })

frontend.json(
    "users/4711",
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid user id: 4711" }},
    expected_http_status=404)

frontend.json(
    "users/alice",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid numeric id: 'alice'" }},
    expected_http_status=400)

frontend.json(
    "users",
    params={ "name": "nosuchuser" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid user name: 'nosuchuser'" }},
    expected_http_status=404)

frontend.json(
    "users",
    params={ "status": "clown" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid user status values: 'clown'" }},
    expected_http_status=400)

frontend.json(
    "users",
    params={ "status": "current,clown,president" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid user status values: 'clown', 'president'" }},
    expected_http_status=400)

frontend.json(
    "users",
    params={ "sort": "age" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid user sort parameter: 'age'" }},
    expected_http_status=400)
