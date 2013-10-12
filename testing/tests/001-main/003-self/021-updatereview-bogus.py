with frontend.signin("alice"):
    frontend.operation(
        "updatereview",
        data={ "review_id": -1,
               "new_owners": ["alice"] },
        expect={ "status": "failure",
                 "code": "nosuchreview" })
