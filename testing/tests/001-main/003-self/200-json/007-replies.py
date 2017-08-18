# @dependency 001-main/003-self/100-reviewing/001-comments.basic.py

# Fetch the id of a review which contains some comments.
result = frontend.operation(
    "searchreview",
    data={ "query": "branch:r/100-reviewing/001-comment.basic" })
testing.expect.check(1, len(result["reviews"]))
review_id = result["reviews"][0]["id"]

result = frontend.json(
    "reviews/%d" % review_id,
    params={ "fields": "issues,notes" },
    expect={ "issues": [int, int, int, int],
             "notes": [int, int] })

issue0 = frontend.json(
    "comments/%d/replies" % result["issues"][0],
    expect={ "replies": [reply_json("dave"),
                         reply_json("bob"),
                         reply_json("erin"),
                         reply_json("bob"),
                         reply_json("alice")] })

issue1 = frontend.json(
    "comments/%d/replies" % result["issues"][1],
    expect={ "replies": [reply_json("alice"),
                         reply_json("bob")] })

issue2 = frontend.json(
    "comments/%d/replies" % result["issues"][2],
    expect={ "replies": [reply_json("bob"),
                         reply_json("erin"),
                         reply_json("alice")] })

note0 = frontend.json(
    "comments/%d/replies" % result["notes"][0],
    expect={ "replies": [] })

issue3 = frontend.json(
    "comments/%d/replies" % result["issues"][3],
    expect={ "replies": [reply_json("bob")] })

note1 = frontend.json(
    "comments/%d/replies" % result["notes"][1],
    expect={ "replies": [] })

def check_with_reply(comment_id, replies):
    for reply_json in replies:
        frontend.json(
            "comments",
            params={ "with_reply": reply_json["id"],
                     "fields": "id" },
            expect={ "id": comment_id })

check_with_reply(result["issues"][0], issue0["replies"])
check_with_reply(result["issues"][1], issue1["replies"])
check_with_reply(result["issues"][2], issue2["replies"])
check_with_reply(result["issues"][3], issue3["replies"])
check_with_reply(result["notes"][0], note0["replies"])
check_with_reply(result["notes"][1], note1["replies"])

with frontend.signin("alice"):
    # Use a comment with no replies to test with.
    comment_id = result["notes"][1]
    published_reply_id = issue0["replies"][-1]["id"]

    reply_id = frontend.json(
        "comments/%d/replies" % comment_id,
        post={
            "text": "JSON reply #1",
        },
        expect={
            "id": int,
            "is_draft": True,
            "author": instance.userid("alice"),
            "timestamp": float,
            "text": "JSON reply #1"
        })["id"]

    frontend.json(
        "replies/%d" % reply_id,
        expect={
            "id": reply_id,
            "is_draft": True,
            "author": instance.userid("alice"),
            "timestamp": float,
            "text": "JSON reply #1"
        })

    frontend.json(
        "comments/%d" % comment_id,
        expect={
            "id": comment_id,
            "type": "note",
            "is_draft": False,
            "state": None,
            "review": review_id,
            "author": instance.userid("alice"),
            "location": {
                "type": "file-version",
                "first_line": int,
                "last_line": int,
                "file": int,
                "changeset": int,
                "side": "new",
                "commit": None,
                "is_translated": False
            },
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": str,
            "replies": [],
            "draft_changes": draft_changes_json("alice", reply=reply_id),
        })

with frontend.signin("bob"):
    # Check that Bob doesn't see the Alice's draft reply.
    frontend.json(
        "comments/%d" % comment_id,
        expect={
            "id": comment_id,
            "type": "note",
            "is_draft": False,
            "state": None,
            "review": review_id,
            "author": instance.userid("alice"),
            "location": {
                "type": "file-version",
                "first_line": int,
                "last_line": int,
                "file": int,
                "changeset": int,
                "side": "new",
                "commit": None,
                "is_translated": False
            },
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": str,
            "replies": [],
            "draft_changes": None,
        })

with frontend.signin("alice"):
    frontend.json(
        "replies/%d" % reply_id,
        put={
            "text": "JSON reply (edited)"
        },
        expect={
            "id": reply_id,
            "is_draft": True,
            "author": instance.userid("alice"),
            "timestamp": float,
            "text": "JSON reply (edited)"
        })

    frontend.json(
        "replies/%d" % reply_id,
        delete=True,
        expected_http_status=204)

    reply_id = frontend.json(
        "replies",
        params={
            "comment": comment_id
        },
        post={
            "text": "JSON reply #2"
        },
        expect={
            "id": int,
            "is_draft": True,
            "author": instance.userid("alice"),
            "timestamp": float,
            "text": "JSON reply #2"
        })["id"]

    frontend.json(
        "replies/%d" % reply_id,
        delete=True,
        expected_http_status=204)

    reply_id = frontend.json(
        "replies",
        post={
            "comment": comment_id,
            "text": "JSON reply #3"
        },
        expect={
            "id": int,
            "is_draft": True,
            "author": instance.userid("alice"),
            "timestamp": float,
            "text": "JSON reply #3"
        })["id"]

    frontend.json(
        "replies",
        post={
            "comment": comment_id,
            "text": "JSON reply (invalid)"
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Comment already has a draft reply"
            }
        })

    frontend.json(
        "replies/%d" % reply_id,
        delete=True,
        expected_http_status=204)

    frontend.json(
        "comments/%d/replies" % comment_id,
        post={
            "text": "   "
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Empty reply"
            }
        })

    frontend.json(
        "replies/%d" % published_reply_id,
        put={
            "text": "Invalid edit"
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Published replies cannot be edited"
            }
        })

    frontend.json(
        "replies/%d" % published_reply_id,
        delete=True,
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Published replies cannot be deleted"
            }
        })

# end of file
