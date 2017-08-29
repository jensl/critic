# @dependency 001-main/002-createrepository.py
# @dependency 001-main/003-self/200-json/006-changesets.py

FROM_SHA1 = "573c5ff15ad95cfbc3e2f2efb0a638a4a78c17a7"
FROM_SINGLE_SHA1 = "aabc2b10c930a9e72fe9587a6e8634087bb3efe1"
TO_SHA1 = "6dc8e9c2d952028286d4b83475947bd0b1410860"
ROOT_SHA1 = "ee37c47f6f6a14afa6912c1cc58a9f49d2a29acd"

GENERIC_FILECHANGE = { "file": int,
                       "changeset": int,
                       "old_sha1": str,
                       "new_sha1": str,
                       "new_mode": None,
                       "old_mode": None }

files = {}

def fetch_file(path):
    result = frontend.json(
        "files",
        params={
            "path": path
        },
        expect={
            "id": int,
            "path": path
        })
    files[path] = result["id"]

fetch_file("testing/__init__.py")
fetch_file("testing/repository.py")
fetch_file("testing/virtualbox.py")

# Filechanges for changeset from single commit
single_changeset = fetch_changeset({ "commit": TO_SHA1 })

frontend.json(
    "filechanges",
    params={
        "repository": 1,
        "changeset": single_changeset["id"]
    },
    expect={"filechanges": [
        {"changeset": single_changeset["id"],
         "old_sha1": "a2ffb3a6cd3b021c34592f4bd8f32905e4dd5830",
         "new_sha1": "2d06e47848827d8d8312542f3687f0380ebbc3ed",
         "file": files["testing/__init__.py"],
         "new_mode": None,
         "old_mode": None},
        {"changeset": single_changeset["id"],
         "old_sha1": "e285e7c535dd8eee185d71c5adec1a328e586a58",
         "new_sha1": "ac6fe72b7ffefb9d5d4c6637aa94c02e756b2665",
         "file": files["testing/repository.py"],
         "new_mode": None,
         "old_mode": None},
        {"changeset": single_changeset["id"],
         "old_sha1": "0f5b7b313b6152f9c4f342c151fa1038a83e03f4",
         "new_sha1": "c2e9ee01afb2b0cdde940532f93a6823013c8a91",
         "file": files["testing/virtualbox.py"],
         "new_mode": None,
         "old_mode": None}]})

# Single filechange for changeset from two commits
custom_changeset = fetch_changeset({
    "from": FROM_SHA1,
    "to": TO_SHA1
})

frontend.json(
    "filechanges/" + str(custom_changeset["files"][0]),
    params={
        "repository": 1,
        "changeset": custom_changeset["id"]
    },
    expect=GENERIC_FILECHANGE)

# Invalid filechange id
frontend.json(
    "filechanges/-1",
    params={
        "repository": 1,
        "changeset": custom_changeset["id"]
    },
    expect={
        "error": {
            "message": "Invalid numeric id: '-1'",
            "title": "Invalid API request"
        }
    },
    expected_http_status=400)
