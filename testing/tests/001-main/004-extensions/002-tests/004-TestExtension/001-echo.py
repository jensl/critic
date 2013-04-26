import json

def check_arguments(expected):
    def check(document):
        try:
            result = json.loads(document)
        except ValueError:
            testing.expect.check("<valid json>", repr(document))
        else:
            actual = result["arguments"]
            testing.expect.check(expected, actual)

    return check

def check_json(expected):
    def check(actual):
        try:
            return expected, json.loads(actual)
        except ValueError:
            return "<valid JSON>", actual
    return check

with frontend.signin("alice"):
    frontend.page(
        "echo",
        expected_content_type="text/json",
        expect={ "json": check_arguments(
            ["GET", "echo", None]) })

    frontend.page(
        "echo?foo=bar",
        expected_content_type="text/json",
        expect={ "json": check_arguments(
            ["GET", "echo", { "raw": "foo=bar",
                              "params": { "foo": "bar" }}]) })

    frontend.page(
        "echo?foo=bar&x=10&y=20",
        expected_content_type="text/json",
        expect={ "json": check_arguments(
            ["GET", "echo", { "raw": "foo=bar&x=10&y=20",
                              "params": { "foo": "bar",
                                          "x": "10",
                                          "y": "20" }}]) })

    frontend.operation(
        "echo",
        data={},
        expect={ "arguments": ["POST", "echo", None],
                 "stdin": check_json({}) })

    frontend.operation(
        "echo",
        data={ "foo": "bar",
               "positions": [{ "x": 10, "y": 20 },
                             { "x": 11, "y": 21 }]},
        expect={ "arguments": ["POST", "echo", None],
                 "stdin": check_json({ "foo": "bar",
                                       "positions": [{ "x": 10, "y": 20 },
                                                     { "x": 11, "y": 21 }]}) })

# Verify that Alice's extension install doesn't affect Bob.
with frontend.signin("bob"):
    frontend.page("echo", expected_http_status=404)
