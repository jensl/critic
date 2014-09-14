def check_user_constructor(document):
    expected = "<User constructor found>"
    if "\nfunction User(" in document:
        actual = expected
    else:
        actual = "<no User constructor found>"
    testing.expect.check(expected, actual)

def check_jquery_foundation(document):
    expected = "<jQuery header found>"
    if "jQuery Foundation, Inc" in document:
        actual = expected
    else:
        actual = "<no jQuery header found>"
    testing.expect.check(expected, actual)

# Test a basic regular file.
frontend.page(
    "static-resource/basic.js",
    expected_content_type=("application/javascript", "text/javascript"),
    expect={ "user_constructor": check_user_constructor })

# Test jquery.js, which is a symlink to the current version.
frontend.page(
    "static-resource/third-party/jquery.js",
    expected_content_type=("application/javascript", "text/javascript"),
    expect={ "jquery_foundation": check_jquery_foundation })

# Test a non-existing file.
frontend.page(
    "static-resource/does-not-exist.js",
    expected_http_status=404)

# Test that directory listing is not enabled.
frontend.page(
    "static-resource/",
    expected_http_status=403)
