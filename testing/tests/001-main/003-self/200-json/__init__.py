critic_json = { "id": 1,
                "name": "critic",
                "path": instance.repository_path(),
                "url": str }

other_json = { "id": 2,
               "name": "other",
               "path": instance.repository_path("other"),
               "url": str }

def user_json(name, fullname=None, status="current", no_email=False):
    if fullname is None:
        fullname = name.capitalize() + " von Testing"
    if no_email:
        email = None
    else:
        email = name + "@example.org"
    return { "id": instance.userid(name),
             "name": name,
             "fullname": fullname,
             "status": status,
             "email": email }

generic_commit_json = {
    "id": int,
    "sha1": str,
    "summary": str,
    "message": str,
    "parents": list,
    "author": {
        "name": str,
        "email": str,
        "timestamp": float
    },
    "committer": {
        "name": str,
        "email": str,
        "timestamp": float
    },
}

def reply_json(author):
    return { "id": int,
             "is_draft": bool,
             "author": instance.userid(author),
             "timestamp": float,
             "text": "This is a reply from %s." % author.capitalize() }

def fetch_changeset(params, repository="critic"):
    params.setdefault("repository", repository)

    result = frontend.json(
        "changesets",
        params=params)

    if result["id"] is None:
        instance.synchronize_service("changeset")

        result = frontend.json(
            "changesets",
            params=params,
            expect={
                "id": int,
                "*": "*"
            })

    return result

def draft_changes_json(author, **kwargs):
    result = {
        "author": instance.userid(author),
        "is_draft": False,
        "reply": None,
        "new_type": None,
        "new_state": None,
        "new_location": None,
    }
    result.update(kwargs)
    return result

# eof
