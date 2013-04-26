def empty(document):
    if document != "":
        testing.expect.check("<empty string>", document)

with frontend.signin("alice"):
    frontend.page(
        "empty",
        expected_content_type="text/plain",
        expect={ "empty": empty })
