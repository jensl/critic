with frontend.signin("alice"):
    frontend.operation(
        "removereviewfilter",
        data={ "filter_id": -1 },
        expect={ "status": "failure",
                 "code": "nosuchfilter" })
