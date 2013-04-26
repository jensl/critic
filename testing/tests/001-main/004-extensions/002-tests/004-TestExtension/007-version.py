def check_version(expected):
    def check(actual):
        testing.expect.check(expected, actual.strip())
    return check

with frontend.signin("alice"):
    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("live") })

with frontend.signin("bob"):
    frontend.page(
        "version",
        expected_http_status=404)

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension",
               "version": "version/stable" })

    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("stable:2") })

    frontend.operation(
        "uninstallextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("live") })

    frontend.operation(
        "uninstallextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension",
               "version": "version/stable",
               "universal": True },
        expect={ "status": "failure",
                 "code": "notallowed" })

with frontend.signin("admin"):
    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension",
               "version": "version/stable",
               "universal": True })

with frontend.signin("bob"):
    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("stable:2") })

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("live") })

    frontend.operation(
        "uninstallextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("stable:2") })
