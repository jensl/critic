document_title = testing.expect.document_title

def check_version(expected):
    def check(actual):
        testing.expect.check(expected, actual.strip())
    return check

with frontend.signin("alice"):
    # Check that alice still has the LIVE version installed.
    frontend.page(
        "version",
        expected_content_type="text/plain",
        expect={ "version": check_version("live") })

instance.execute(["sudo", "rm", "-rf", "~alice/CriticExtensions"])

with frontend.signin("alice"):
    # Check that the extension is ignored, and that /version just returns 404.
    frontend.page(
        "version",
        expected_http_status=404)

    # Check that /home, where the extension injects things, loads as expected.
    frontend.page(
        "home",
        expect={ "title": document_title(u"Alice von Testing's Home") })

    # Check that /manageextensions also loads as expected.
    frontend.page(
        "manageextensions",
        expect={ "title": document_title(u"Manage Extensions") })

    # ... even with what=installed.
    frontend.page(
        "manageextensions",
        params={ "what": "installed" },
        expect={ "title": document_title(u"Manage Extensions") })

    # Check that the extension can be uninstalled.
    frontend.operation(
        "uninstallextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    # Check that /manageextensions still loads.
    frontend.page(
        "manageextensions",
        params={ "what": "installed" },
        expect={ "title": document_title(u"Manage Extensions") })
