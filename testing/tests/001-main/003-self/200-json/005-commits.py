# @dependency 001-main/002-createrepository.py

SHA1 = "78d7849db854f3544d7291cce96a0a4fa6d6843d"

commit_json = {
    "id": int,
    "sha1": SHA1,
    "summary": "High-level testing framework",
    "message": """\
High-level testing framework

Framework for automated installation and "black-box" testing of Critic
running in a VirtualBox instance.
""",
    "parents": [int],
    "author": {
        "name": "Jens Lindstrom",
        "email": "jl@opera.com",
        "timestamp": float
    },
    "committer": {
        "name": "Jens Lindstrom",
        "email": "jl@opera.com",
        "timestamp": float
    },
}

result = frontend.json(
    "commits",
    params={ "sha1": SHA1,
             "repository": "critic" },
    expect=commit_json)

frontend.json(
    "commits/%d" % result["id"],
    params={ "repository": "critic" },
    expect=commit_json)

result = frontend.json(
    "repositories/1/commits",
    params={ "sha1": SHA1,
             "repository": "critic" },
    expect=commit_json)

frontend.json(
    "repositories/1/commits/%d" % result["id"],
    params={ "repository": "critic" },
    expect=commit_json)

frontend.json(
    "commits/47114711",
    params={ "repository": "critic" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid commit id: 47114711" }},
    expected_http_status=404)

frontend.json(
    "commits/47114711",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Commit reference must have repository specified." }},
    expected_http_status=400)

frontend.json(
    "commits",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Missing required SHA-1 parameter." }},
    expected_http_status=400)

frontend.json(
    "commits",
    params={ "sha1": SHA1 },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Commit reference must have repository specified." }},
    expected_http_status=400)

frontend.json(
    "commits",
    params={ "sha1": "00",
             "repository": "critic" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid SHA-1 parameter: '00'" }},
    expected_http_status=400)

frontend.json(
    "commits",
    params={ "sha1": "invalid SHA-1",
             "repository": "critic" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid SHA-1 parameter: 'invalid SHA-1'" }},
    expected_http_status=400)

frontend.json(
    "commits",
    params={ "sha1": "47114711",
             "repository": "critic" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid commit SHA-1: '47114711'" }},
    expected_http_status=404)
