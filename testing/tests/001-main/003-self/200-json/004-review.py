# @dependency 001-main/003-self/020-reviewrebase.py
# @dependency 001-main/003-self/100-reviewing/001-comments.basic.py

# Fetch the id of a review which contains some comments.
result = frontend.operation(
    "searchreview",
    data={ "query": "branch:r/100-reviewing/001-comment.basic" })
testing.expect.check(1, len(result["reviews"]))
review_id = result["reviews"][0]["id"]

review_json = {
    "id": review_id,
    "state": "open",
    "summary": "Added 100-reviewing/001-comment.basic.txt",
    "description": None,
    "repository": 1,
    "branch": int,
    "owners": [instance.userid("alice")],
    "assigned_reviewers": [instance.userid("bob")],
    "active_reviewers": [],
    "progress": 0,
    "progress_per_commit": list,
    "watchers": [instance.userid("dave"),
                 instance.userid("erin")],
    "partitions": [{ "commits": [int],
                     "rebase": None }],
    "issues": [int, int, int, int],
    "notes": [int, int],
    "pending_update": None,
    "pending_rebase": None,
}

frontend.json(
    "reviews/%d" % review_id,
    expect=review_json)

frontend.json(
    "reviews/%d" % review_id,
    params={ "include": "users,commits" },
    expect={ "id": review_id,
             "state": "open",
             "summary": "Added 100-reviewing/001-comment.basic.txt",
             "description": None,
             "repository": 1,
             "branch": int,
             "owners": [instance.userid("alice")],
             "assigned_reviewers": [instance.userid("bob")],
             "active_reviewers": [],
             "progress": 0,
             "progress_per_commit": list,
             "watchers": [instance.userid("dave"),
                          instance.userid("erin")],
             "partitions": [{ "commits": [int],
                              "rebase": None }],
             "issues": [int, int, int, int],
             "notes": [int, int],
             "pending_update": None,
             "pending_rebase": None,
             "linked": { "users": [user_json("alice"),
                                   user_json("bob"),
                                   user_json("dave"),
                                   user_json("erin")],
                         "commits": [generic_commit_json] }})

frontend.json(
    "reviews/%d/commits" % review_id,
    expect={ "commits": [generic_commit_json] })

def check_description(path, description, check):
    if description is not None:
        check(path, expected=str, actual=description)

def check_reviews(expected_state=str):
    def checker(path, reviews, check):
        if not check(path, expected=list, actual=reviews):
            return
        for index, review in enumerate(reviews):
            check("%s[%d]" % (path, index),
                  expected={
                      "id": int,
                      "state": str,
                      "summary": str,
                      "description": check_description,
                      "repository": 1,
                      "branch": int,
                      "owners": list,
                      "assigned_reviewers": list,
                      "active_reviewers": list,
                      "progress": 0,
                      "progress_per_commit": list,
                      "watchers": list,
                      "partitions": list,
                      "issues": list,
                      "notes": list,
                      "pending_update": None,
                      "pending_rebase": None,
                  },
                  actual=review)
    return checker

all_reviews = frontend.json(
    "reviews",
    expect={ "reviews": check_reviews() })

if not any(review["id"] == review_id for review in all_reviews["reviews"]):
    logger.error("/api/v1/reviews did not contain r/%d" % review_id)

frontend.json(
    "reviews",
    params={ "repository": "critic" },
    expect={ "reviews": check_reviews() })

open_reviews = frontend.json(
    "reviews",
    params={ "state": "open" },
    expect={ "reviews": check_reviews("open") })

if not any(review["id"] == review_id for review in open_reviews["reviews"]):
    logger.error("/api/v1/reviews?state=open did not contain r/%d" % review_id)

closed_reviews = frontend.json(
    "reviews",
    params={ "state": "closed" },
    expect={ "reviews": check_reviews("closed") })

if any(review["id"] == review_id for review in closed_reviews["reviews"]):
    logger.error("/api/v1/reviews?state=closed contained r/%d" % review_id)

dropped_reviews = frontend.json(
    "reviews",
    params={ "state": "dropped" },
    expect={ "reviews": check_reviews("dropped") })

if any(review["id"] == review_id for review in dropped_reviews["reviews"]):
    logger.error("/api/v1/reviews?state=dropped contained r/%d" % review_id)

frontend.json(
    "reviews/4711",
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid review id: 4711" }},
    expected_http_status=404)

frontend.json(
    "reviews/mypatch",
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid numeric id: 'mypatch'" }},
    expected_http_status=400)

frontend.json(
    "reviews",
    params={ "repository": "nosuchrepository" },
    expect={ "error": { "title": "No such resource",
                        "message": "Resource not found: Invalid repository name: 'nosuchrepository'" }},
    expected_http_status=404)

frontend.json(
    "reviews",
    params={ "state": "rejected" },
    expect={ "error": { "title": "Invalid API request",
                        "message": "Invalid review state values: 'rejected'" }},
    expected_http_status=400)

no_repository_access = {
    "repositories": {
        "rule": "deny",
        "exceptions": []
    }
}

with testing.utils.access_token("alice", no_repository_access) as access_token:
    with frontend.signin(access_token=access_token):
        # Check that this review is inaccessible now.
        frontend.json(
            "reviews/%d" % review_id,
            expected_http_status=403)

        # Check that we can still list "all" reviews successfully.
        frontend.json(
            "reviews",
            expect={
                "reviews": []
            })
