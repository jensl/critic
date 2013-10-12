INVALID_USER_ID = 0

with frontend.signin("alice"):
    frontend.operation(
        "addreviewfilters",
        data={ "review_id": 1,
               "filters": [{ "type": "watcher",
                             "user_ids": [INVALID_USER_ID],
                             "paths": ["/"] }] },
        expect={ "status": "failure",
                 "code": "invaliduserid" })
