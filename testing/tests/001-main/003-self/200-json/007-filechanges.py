# @dependency 001-main/002-createrepository.py
# @dependency 001-main/003-self/200-json/006-changesets.py

FROM_SHA1 = "573c5ff15ad95cfbc3e2f2efb0a638a4a78c17a7"
FROM_SINGLE_SHA1 = "aabc2b10c930a9e72fe9587a6e8634087bb3efe1"
TO_SHA1 = "6dc8e9c2d952028286d4b83475947bd0b1410860"
ROOT_SHA1 = "ee37c47f6f6a14afa6912c1cc58a9f49d2a29acd"

GENERIC_FILECHANGE = { "id": int,
                       "changeset": int,
                       "old_sha1": str,
                       "new_sha1": str,
                       "chunks": list,
                       "path": str,
                       "new_mode": None,
                       "old_mode": None }

# Filechanges for changeset from single commit
single_changeset = frontend.json(
    "changesets",
    params={ "repository": 1,
             "commit": TO_SHA1})
frontend.json(
    "filechanges",
    params={ "repository": 1,
             "changeset": single_changeset["id"]},
    expect={"filechanges": [
        {"changeset": int,
         "old_sha1": "a2ffb3a6cd3b021c34592f4bd8f32905e4dd5830",
         "new_sha1": "2d06e47848827d8d8312542f3687f0380ebbc3ed",
         "chunks": [
             {"insertoffset": 85,
              "deleteoffset": 85,
              "deletecount": 0,
              "is_whitespace": 0,
              "analysis": None,
              "insertcount": 4}
         ],
         "path": "testing/__init__.py",
         "new_mode": None,
         "id": int,
         "old_mode": None},
        {"changeset": int,
         "old_sha1": "e285e7c535dd8eee185d71c5adec1a328e586a58",
         "new_sha1": "ac6fe72b7ffefb9d5d4c6637aa94c02e756b2665",
         "chunks": [
             {"insertoffset": 92,
              "deleteoffset": 92,
              "deletecount": 34,
              "is_whitespace": 0,
              "analysis": "0=5:ws,i0-4;1=6:ws,i0-4;2=7:ws,i0-4;3=8:ws,i0-4;4=9:ws,i0-4;5=10:ws,i0-4;6=11:ws,i0-4;7=12:ws,i0-4;8=13:ws,i0-4;9=14:ws,i0-4;10=15:ws,i0-4;11=16:ws,i0-4;13=17:ws,i0-4;14=18;15=19:ws,i0-4;16=20:ws,i0-4;17=21:ws,i0-4;18=22:ws,i0-4;19=23:ws,i0-4;20=24:ws,i0-4;21=25:ws,i0-4;22=26:ws,i0-4;23=27:ws,i0-4;24=28:ws,i0-4;25=29:ws,i0-4;26=30:ws,i0-4;27=31:ws,i0-4;28=32:ws,i0-4;29=33:ws,i0-4;30=34:ws,i0-4",
              "insertcount": 35}],
         "path": "testing/repository.py",
         "new_mode": None,
         "id": int,
         "old_mode": None},
        {"changeset": int,
         "old_sha1": "0f5b7b313b6152f9c4f342c151fa1038a83e03f4",
         "new_sha1": "c2e9ee01afb2b0cdde940532f93a6823013c8a91",
         "chunks": [
             {"insertoffset": 52,
              "deleteoffset": 52,
              "deletecount": 0,
              "is_whitespace": 0,
              "analysis": None,
              "insertcount": 1}],
         "path": "testing/virtualbox.py",
         "new_mode": None,
         "id": int,
         "old_mode": None}]})

# Single filechange for changeset from two commits
custom_changeset = frontend.json(
    "changesets",
    params={ "repository": "critic",
             "from": FROM_SHA1,
             "to": TO_SHA1 })
frontend.json(
    "filechanges/" + str(custom_changeset["filediffs"][0]),
    params={ "repository": 1,
             "changeset": custom_changeset["id"]},
    expect=GENERIC_FILECHANGE)

# Invalid filechange id
frontend.json(
    "filechanges/-1",
    params={ "repository": 1,
             "changeset": custom_changeset["id"]},
    expect={ "error": {
        "message": "Invalid numeric id: '-1'",
        "title": "Invalid API request"}
         },
    expected_http_status=400)
