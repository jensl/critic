# @dependency 001-main/002-createrepository.py

frontend.json(
    "repositories",
    expect={ "repositories": [critic_json] })

frontend.json(
    "repositories/1",
    expect=critic_json)

frontend.json(
    "repositories",
    params={ "name": "critic" },
    expect=critic_json)

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
