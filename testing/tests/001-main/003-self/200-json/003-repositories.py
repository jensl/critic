# @dependency 001-main/002-createrepository.py

frontend.json(
    "repositories",
    expect={ "repositories": [critic_json, other_json] })

frontend.json(
    "repositories/1",
    expect=critic_json)

frontend.json(
    "repositories",
    params={ "name": "critic" },
    expect=critic_json)

frontend.json(
    "repositories/2",
    expect=other_json)

frontend.json(
    "repositories",
    params={ "name": "other" },
    expect=other_json)

frontend.json(
    "repositories/4711",
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid repository id: 4711" }},
    expected_http_status=404)

frontend.json(
    "repositories/critic",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid numeric id: 'critic'" }},
    expected_http_status=400)

frontend.json(
    "repositories",
    params={ "name": "nosuchrepository" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid repository name: 'nosuchrepository'" }},
    expected_http_status=404)

frontend.json(
    "repositories",
    params={ "filter": "interesting" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid repository filter parameter: 'interesting'" }},
    expected_http_status=400)

# Test with an access control profile that restricts access to other.git.
no_other = {
    "repositories": {
        "rule": "allow",
        "exceptions": [{
            "repository": "other"
        }]
    }
}

with testing.utils.access_token("alice", no_other) as access_token:
    with frontend.signin(access_token=access_token):
        # Check that we can still access critic.git.
        frontend.json(
            "repositories",
            params={ "name": "critic" },
            expect=critic_json)

        # Check that we can't access other.git.
        frontend.json(
            "repositories",
            params={ "name": "other" },
            expected_http_status=403)

        # Check that we can still list all repositories, but that other.git is
        # not included.
        frontend.json(
            "repositories",
            expect={ "repositories": [critic_json] })
