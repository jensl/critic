# @dependency 001-main/002-createrepository.py

FROM_SHA1 = "573c5ff15ad95cfbc3e2f2efb0a638a4a78c17a7"
FROM_SINGLE_SHA1 = "aabc2b10c930a9e72fe9587a6e8634087bb3efe1"
TO_SHA1 = "6dc8e9c2d952028286d4b83475947bd0b1410860"
ROOT_SHA1 = "ee37c47f6f6a14afa6912c1cc58a9f49d2a29acd"

# Changeset for single commit
frontend.json(
    "changesets",
    params={ "repository": 1,
             "commit": TO_SHA1},
    expect={ "filediffs": None,
             "files": None,
             "type": "direct",
             "to_commit": None,
             "id": None,
             "from_commit": None,
             "contributing_commits": None,
             "review_state": None })
instance.synchronize_service("changeset") # wait for changeset creation to finish
single_changeset = frontend.json(
    "changesets",
    params={ "repository": 1,
             "commit": TO_SHA1},
    expect={ "filediffs": [int, int, int],
             "files": list,
             "type": "direct",
             "to_commit": int,
             "id": int,
             "from_commit": int,
             "contributing_commits": [int],
             "review_state": None })
equiv_changeset = frontend.json(
    "changesets",
    params={ "repository": 1,
             "from": FROM_SINGLE_SHA1,
             "to": TO_SHA1},
    expect={ "filediffs": [int, int, int],
             "files": list,
             "type": "direct",
             "to_commit": int,
             "id": int,
             "from_commit": int,
             "contributing_commits": [int],
             "review_state": None })
assert (single_changeset == equiv_changeset),\
    "single changeset should equal equivalent changeset"

# Changeset between two commits
frontend.json(
    "changesets",
    params={ "repository": "critic",
             "from": FROM_SHA1,
             "to": TO_SHA1 },
    expect={ "filediffs": None,
             "files": None,
             "type": "custom",
             "to_commit": None,
             "id": None,
             "from_commit": None,
             "contributing_commits": None,
             "review_state": None })
instance.synchronize_service("changeset") # wait for changeset creation to finish
frontend.json(
    "changesets",
    params={ "repository": "critic",
             "from": FROM_SHA1,
             "to": TO_SHA1 },
    expect={ "filediffs": [int, int, int, int, int, int, int, int],
             "files": list,
             "type": "custom",
             "to_commit": int,
             "id": int,
             "from_commit": int,
             "contributing_commits": [int, int, int],
             "review_state": None })

# Changeset from id
frontend.json(
    "changesets/" + str(single_changeset["id"]),
    params={ "repository": 1 },
    expect={ "filediffs": [int, int, int],
             "files": list,
             "type": "direct",
             "to_commit": int,
             "id": single_changeset["id"],
             "from_commit": int,
             "contributing_commits": [int],
             "review_state": None })

# Changeset from partial SHA1
frontend.json(
    "changesets",
    params={ "repository": 1,
             "commit": TO_SHA1[:8]},
    expect={ "filediffs": [int, int, int],
             "files": list,
             "type": "direct",
             "to_commit": int,
             "id": int,
             "from_commit": int,
             "contributing_commits": [int],
             "review_state": None })

# Missing changeset id and commit refs
frontend.json(
    "changesets",
    params={ "repository": 1 },
    expect={ "error": {
        "message": "Missing required parameters from and to, or commit",
        "title": "Invalid API request" }
         },
    expected_http_status=400)

# Missing repository
frontend.json(
    "changesets",
    params={ "commit": TO_SHA1 },
    expect={ "error": {
        "message": "repository needs to be specified, ex. &repository=<id>",
        "title": "Invalid API request" }
         },
    expected_http_status=400)

# Missing to
frontend.json(
    "changesets",
    params={ "repository": 1,
             "from": FROM_SHA1 },
    expect={ "error": {
        "message": "Missing required parameters from and to, only one supplied",
        "title": "Invalid API request" }
         },
    expected_http_status=400)

# Invalid SHA1
frontend.json(
    "changesets",
    params={ "repository": 1,
             "commit": "00g0"},
    expect={ "error": {
        "message": "Invalid parameter: commit=00g0: Invalid ref: '00g0^{commit}'",
        "title": "No such resource" }
         },
    expected_http_status=404)

# Changeset between a commit and itself
frontend.json(
    "changesets",
    params={ "repository": 1,
             "from": FROM_SHA1,
             "to": FROM_SHA1},
    expect={ "error": {
        "message": "from and to can't be the same commit",
        "title": "Invalid API input" }
         },
    expected_http_status=400)
