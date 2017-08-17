# @dependency 001-main/003-self/004-createreview.py
# @dependency 001-main/003-self/100-reviewing/001-comments.basic.py

import os

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

frontend.json(
    "comments/%d" % result["issues"][0],
    expect={ "id": result["issues"][0],
             "type": "issue",
             "is_draft": False,
             "state": "open",
             "review": review_id,
             "author": instance.userid("alice"),
             "location": None,
             "resolved_by": None,
             "addressed_by": None,
             "timestamp": float,
             "text": "This is a general issue.",
             "replies": [int, int, int, int, int] })

frontend.json(
    "comments/%d" % result["issues"][1],
    expect={ "id": result["issues"][1],
             "type": "issue",
             "is_draft": False,
             "state": "open",
             "review": review_id,
             "author": instance.userid("alice"),
             "location": None,
             "resolved_by": None,
             "addressed_by": None,
             "timestamp": float,
             "text": "This is a general note.",
             "replies": [int, int] })

frontend.json(
    "comments/%d" % result["issues"][2],
    expect={ "id": result["issues"][2],
             "type": "issue",
             "is_draft": False,
             "state": "resolved",
             "review": review_id,
             "author": instance.userid("alice"),
             "location": {
                 "type": "commit-message",
                 "first_line": int,
                 "last_line": int,
                 "commit": int
             },
             "resolved_by": instance.userid("dave"),
             "addressed_by": None,
             "timestamp": float,
             "text": "This is a commit issue.",
             "replies": [int, int, int] })

frontend.json(
    "comments/%d" % result["issues"][3],
    expect={ "id": result["issues"][3],
             "type": "issue",
             "is_draft": False,
             "state": "open",
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
             "text": "This is a file issue.",
             "replies": [int] })

frontend.json(
    "comments/%d" % result["notes"][0],
    expect={ "id": result["notes"][0],
             "type": "note",
             "is_draft": False,
             "state": None,
             "review": review_id,
             "author": instance.userid("alice"),
             "location": {
                 "type": "commit-message",
                 "first_line": int,
                 "last_line": int,
                 "commit": int
             },
             "resolved_by": None,
             "addressed_by": None,
             "timestamp": float,
             "text": "This is a commit note.",
             "replies": [] })

frontend.json(
    "comments/%d" % result["notes"][1],
    expect={ "id": result["notes"][1],
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
             "text": "This is a file note.",
             "replies": [] })

frontend.json(
    "reviews/%d/comments" % review_id,
    params={ "fields": "id" },
    expect={ "comments": [{ "id": result["issues"][0] },
                          { "id": result["issues"][1] },
                          { "id": result["issues"][2] },
                          { "id": result["notes"][0] },
                          { "id": result["issues"][3] },
                          { "id": result["notes"][1] }] })

frontend.json(
    "comments/%d" % result["issues"][0],
    params={ "include": "users,replies" },
    expect={ "id": result["issues"][0],
             "type": "issue",
             "is_draft": False,
             "state": "open",
             "review": review_id,
             "author": instance.userid("alice"),
             "location": None,
             "resolved_by": None,
             "addressed_by": None,
             "timestamp": float,
             "text": "This is a general issue.",
             "replies": [int, int, int, int, int],
             "linked": { "users": [user_json("alice"),
                                   user_json("bob"),
                                   user_json("dave"),
                                   user_json("erin")],
                         "replies": [reply_json("bob"),
                                     reply_json("dave"),
                                     reply_json("erin"),
                                     reply_json("alice"),
                                     reply_json("bob")] }})

with frontend.signin("alice"):
    # Create comment with review specified via query parameter.
    created_issue_id_1 = frontend.json(
        "comments",
        params={
            "review": review_id
        },
        post={
            "type": "issue",
            "text": "JSON general issue #1"
        },
        expect={
            "id": int,
            "type": "issue",
            "is_draft": True,
            "state": "open",
            "review": review_id,
            "author": instance.userid("alice"),
            "location": None,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": "JSON general issue #1",
            "replies": []
        })["id"]

    # Create comment with review specified via POST data. Also specify author
    # explicitly.
    created_note_id_1 = frontend.json(
        "comments",
        post={
            "type": "note",
            "review": review_id,
            "author": instance.userid("alice"),
            "text": "JSON general note #1"
        },
        expect={
            "id": int,
            "type": "note",
            "is_draft": True,
            "state": None,
            "review": review_id,
            "author": instance.userid("alice"),
            "location": None,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": "JSON general note #1",
            "replies": []
        })["id"]

    # Create issue with review specified in the path.
    created_issue_id_2 = frontend.json(
        "reviews/%d/issues" % review_id,
        post={
            "text": "JSON general issue #2"
        },
        expect={
            "id": int,
            "type": "issue",
            "is_draft": True,
            "state": "open",
            "review": review_id,
            "author": instance.userid("alice"),
            "location": None,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": "JSON general issue #2",
            "replies": []
        })["id"]

    # Create note with review specified in the path.
    created_note_id_2 = frontend.json(
        "reviews/%d/notes" % review_id,
        post={
            "text": "JSON general note #2"
        },
        expect={
            "id": int,
            "type": "note",
            "is_draft": True,
            "state": None,
            "review": review_id,
            "author": instance.userid("alice"),
            "location": None,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": "JSON general note #2",
            "replies": []
        })["id"]

    review_data = frontend.json(
        "reviews/%d" % review_id,
        params={
            "fields": "issues,notes"
        },
        expect={
            "issues": [int, int, int, int, int, int],
            "notes": [int, int, int, int]
        })

    testing.expect.true(
        created_issue_id_1 in review_data["issues"],
        "created issue #1 in reviews/N/issues")
    testing.expect.true(
        created_note_id_1 in review_data["notes"],
        "created note #1 in reviews/N/notes")
    testing.expect.true(
        created_issue_id_2 in review_data["issues"],
        "created issue #2 in reviews/N/issues")
    testing.expect.true(
        created_note_id_2 in review_data["notes"],
        "created note #2 in reviews/N/notes")

with frontend.signin("bob"):
    # Check that Bob doesn't see Alice's draft comments.
    review_data = frontend.json(
        "reviews/%d" % review_id,
        params={
            "fields": "issues,notes"
        },
        expect={
            "issues": [int, int, int, int],
            "notes": [int, int]
        })

    published_issue_ids = review_data["issues"]
    published_note_ids = review_data["notes"]

    testing.expect.false(
        created_issue_id_1 in review_data["issues"],
        "created issue #1 in reviews/N/issues")
    testing.expect.false(
        created_note_id_1 in review_data["notes"],
        "created note #1 in reviews/N/notes")
    testing.expect.false(
        created_issue_id_2 in review_data["issues"],
        "created issue #2 in reviews/N/issues")
    testing.expect.false(
        created_note_id_2 in review_data["notes"],
        "created note #2 in reviews/N/notes")

# Find another review.
result = frontend.operation(
    "searchreview",
    data={ "query": "branch:r/004-createreview" })
testing.expect.check(1, len(result["reviews"]))
other_review_id = result["reviews"][0]["id"]

with frontend.signin("alice"):
    frontend.json(
        "comments/%d" % created_issue_id_1,
        put={
            "text": "JSON general issue #1 (edited)"
        },
        expect={
            "id": int,
            "type": "issue",
            "is_draft": True,
            "state": "open",
            "review": review_id,
            "author": instance.userid("alice"),
            "location": None,
            "resolved_by": None,
            "addressed_by": None,
            "timestamp": float,
            "text": "JSON general issue #1 (edited)",
            "replies": []
        })

    frontend.json(
        "comments/%d" % created_note_id_1,
        delete=True,
        expected_http_status=204)

    review_data = frontend.json(
        "reviews/%d" % review_id,
        params={
            "fields": "issues,notes"
        },
        expect={
            "issues": [int, int, int, int, int, int],
            "notes": [int, int, int]
        })

    testing.expect.true(
        created_issue_id_1 in review_data["issues"],
        "created issue #1 in reviews/N/issues")
    testing.expect.false(
        created_note_id_1 in review_data["notes"],
        "created note #1 in reviews/N/notes")
    testing.expect.true(
        created_issue_id_2 in review_data["issues"],
        "created issue #2 in reviews/N/issues")
    testing.expect.true(
        created_note_id_2 in review_data["notes"],
        "created note #2 in reviews/N/notes")

    frontend.json(
        "comments/%d,%d,%d" % (created_issue_id_1,
                               created_issue_id_2,
                               created_note_id_2),
        put={
            "text": "Common text (edited)"
        },
        expect={
            "comments": [
                {
                    "id": created_issue_id_1,
                    "text": "Common text (edited)",
                    "*": "*"
                },
                {
                    "id": created_issue_id_2,
                    "text": "Common text (edited)",
                    "*": "*"
                },
                {
                    "id": created_note_id_2,
                    "text": "Common text (edited)",
                    "*": "*"
                }
            ]
        })

    # Error handling.

    # Create comment without specifying a review.
    frontend.json(
        "comments",
        post={
            "type": "issue",
            "text": "Invalid issue"
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "No review specified"
            }
        })

    # Create comment without specifying conflicting reviews.
    frontend.json(
        "comments",
        params={
            "review": review_id
        },
        post={
            "type": "issue",
            "review": other_review_id,
            "text": "Invalid issue"
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Conflicting reviews specified"
            }
        })

    # Create comment as another user.
    frontend.json(
        "comments",
        post={
            "type": "issue",
            "review": review_id,
            "author": instance.userid("bob"),
            "text": "Invalid issue"
        },
        expected_http_status=403,
        expect={
            "error": {
                "title": "Permission denied",
                "message": "Must be an administrator"
            }
        })

    # Create comment with empty text.
    frontend.json(
        "comments",
        post={
            "type": "issue",
            "review": review_id,
            "text": "   "
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Empty comment"
            }
        })

    # Try to edit text of published comment.
    frontend.json(
        "comments/%d" % published_note_ids[0],
        put={
            "text": "Invalid edit"
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Published comments cannot be edited"
            }
        })

    # Try to edit text to empty.
    frontend.json(
        "comments/%d" % created_issue_id_1,
        put={
            "text": "   "
        },
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Empty comment"
            }
        })

    # Try to delete a published comment.
    frontend.json(
        "comments/%d" % published_note_ids[0],
        delete=True,
        expected_http_status=400,
        expect={
            "error": {
                "title": "Invalid API request",
                "message": "Published comments cannot be deleted"
            }
        })

    frontend.operation(
        "abortchanges",
        data={
            "review_id": review_id,
            "what": {
                "approval": False,
                "comments": True,
                "metacomments": False
            }
        })

#
# Create review which modifies a file a couple of times.
#

with repository.workcopy() as work:
    review = Review(work, "alice", "200-json/006-comments")
    review.addFile(the_file="200-json/006-comments.txt")
    review.commit("reference commit",
                  reference=True,
                  the_file=["1st line",
                            "2nd line",
                            "3rd line",
                            "4th line",
                            "5th line",
                            "6th line",
                            "7th line",
                            "8th line"])
    review.commit("first reviewed commit",
                  the_file=["1st line",
                            "2nd line (edited)",
                            "3rd line (edited)",
                            "4th line",
                            "5th line",
                            "6th line",
                            "7th line",
                            "8th line"])
    review.commit("second reviewed commit",
                     the_file=["1st line",
                               "2nd line (edited)",
                               "3rd line (edited)",
                               "4th line",
                               "  1st added line",
                               "  2nd added line",
                               "  3rd added line",
                               "5th line",
                               "6th line (edited)",
                               "7th line (edited)",
                               "8th line"]),
    review.commit("third reviewed commit",
                  the_file=["1st line",
                            "2nd line (edited)",
                            "3rd line (edited)",
                            "4th line",
                            "  1st added line",
                            "  2nd added line",
                            "  3rd added line",
                            "5th line (edited)",
                            "6th line (edited) (edited)",
                            "7th line (edited)",
                            "8th line"])
    review.submit()
    review_id = review.id
    sha1s = review.sha1s

with frontend.signin("alice"):
    issue_1 = frontend.json(
        "reviews/%d/issues" % review_id,
        post={
            "text": "Issue on 1st line",
            "location": {
                "type": "file-version",
                "changeset": fetch_changeset({ "from": sha1s[0],
                                               "to": sha1s[1] })["id"],
                "file": "200-json/006-comments.txt",
                "first_line": 1,
                "last_line": 1,
                "side": "new",
            },
        })["id"]

    issue_2 = frontend.json(
        "reviews/%d/issues" % review_id,
        post={
            "text": "Issue on 1st-3rd line",
            "location": {
                "type": "file-version",
                "changeset": fetch_changeset({ "from": sha1s[0],
                                               "to": sha1s[2] })["id"],
                "file": "200-json/006-comments.txt",
                "first_line": 1,
                "last_line": 3,
                "side": "new",
            },
        })["id"]

    issue_3 = frontend.json(
        "reviews/%d/issues" % review_id,
        post={
            "text": "Issue on 8th line",
            "location": {
                "type": "file-version",
                "changeset": fetch_changeset({ "from": sha1s[1],
                                               "to": sha1s[3] })["id"],
                "file": "200-json/006-comments.txt",
                "first_line": 11,
                "last_line": 11,
                "side": "new",
            },
        })["id"]

    issue_4 = frontend.json(
        "reviews/%d/issues" % review_id,
        post={
            "text": "Issue on 6th-7th line",
            "location": {
                "type": "file-version",
                "commit": sha1s[2],
                "file": "200-json/006-comments.txt",
                "first_line": 9,
                "last_line": 10,
            },
        })["id"]

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "commit": sha1s[1],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 8,
                    "last_line": 8,
                }
            }],
        })

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "commit": sha1s[2],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 11,
                    "last_line": 11,
                }
            }, {
                "id": issue_4,
                "location": {
                    "first_line": 9,
                    "last_line": 10,
                }
            }],
        })

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "commit": sha1s[3],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 11,
                    "last_line": 11,
                }
            }],
        })

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "changeset": fetch_changeset({ "from": sha1s[0],
                                           "to": sha1s[2] })["id"],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 11,
                    "last_line": 11,
                }
            }, {
                "id": issue_4,
                "location": {
                    "first_line": 9,
                    "last_line": 10,
                }
            }],
        })

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "changeset": fetch_changeset({ "from": sha1s[1],
                                           "to": sha1s[3] })["id"],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 11,
                    "last_line": 11,
                }
            }],
        })

    frontend.json(
        "reviews/%d/comments" % review_id,
        params={
            "changeset": fetch_changeset({ "from": sha1s[0],
                                           "to": sha1s[3] })["id"],
            "fields": "id,location.first_line,location.last_line",
        },
        expect={
            "comments": [{
                "id": issue_1,
                "location": {
                    "first_line": 1,
                    "last_line": 1,
                }
            }, {
                "id": issue_2,
                "location": {
                    "first_line": 1,
                    "last_line": 3,
                }
            }, {
                "id": issue_3,
                "location": {
                    "first_line": 11,
                    "last_line": 11,
                }
            }],
        })

# end of file
