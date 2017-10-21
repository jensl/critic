import json

def basic():
    from operation.basictypes import (
        OperationResult, OperationError, OperationFailure,
        OperationFailureMustLogin)

    def convert(value):
        return json.loads(str(value))

    #
    # OperationResult
    #

    # OperationResult has status=ok by default.
    assert convert(OperationResult()) == { "status": "ok" }

    # But status can be overridden.
    assert convert(OperationResult(status="bananas")) == { "status": "bananas" }

    # Other values can be set as well.
    assert convert(OperationResult(foo=10)) == { "status": "ok", "foo": 10 }

    # Even to None/null.
    assert convert(OperationResult(foo=None)) == { "status": "ok", "foo": None }

    # And test OperationResult.set().
    result = OperationResult()
    result.set("foo", 10)
    assert convert(result) == { "status": "ok", "foo": 10 }
    result.set("foo", [1, 2, 3])
    assert convert(result) == { "status": "ok", "foo": [1, 2, 3] }
    result.set("foo", None)
    assert convert(result) == { "status": "ok", "foo": None }

    #
    # OperationError
    #

    assert convert(OperationError("wrong!")) == { "status": "error",
                                                  "error": "wrong!" }

    #
    # OperationFailure
    #

    assert (convert(OperationFailure("the code", "the title", "the message"))
            == { "status": "failure", "code": "the code", "title": "the title",
                 "message": "the message" })

    # Check HTML escaping.
    assert (convert(OperationFailure("<code>", "<title>", "<message>"))
            == { "status": "failure", "code": "<code>",
                 "title": "&lt;title&gt;", "message": "&lt;message&gt;" })

    # Check HTML escaping with is_html=True (title still escaped, but not the
    # message.)
    assert (convert(OperationFailure("<code>", "<title>", "<message>", True))
            == { "status": "failure", "code": "<code>",
                 "title": "&lt;title&gt;", "message": "<message>" })

    print("basic: ok")
