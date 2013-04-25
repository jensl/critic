import os
import tempfile

instance.execute(
    ["mkdir", "-p", "~/CriticExtensions/InvalidExtension",
     "&&",
     "chmod", "u+rwX,go+rX", "~/CriticExtensions"],
    as_user="alice")

EXTENSION_PATH = "/home/alice/CriticExtensions/InvalidExtension"
MANIFEST_PATH = os.path.join(EXTENSION_PATH, "MANIFEST")

class TransferredFile(object):
    def __init__(self, target_name, source):
        self.target_path = os.path.join(EXTENSION_PATH, target_name)
        self.source = source
    def __enter__(self, *args):
        source_file = tempfile.NamedTemporaryFile()
        source_file.write(self.source)
        source_file.flush()
        instance.copyto(source_file.name, self.target_path, as_user="alice")
        instance.execute(["chmod", "g+r", self.target_path], as_user="alice")
        source_file.close()
        return self
    def __exit__(self, *args):
        instance.execute(["rm", "-f", self.target_path], as_user="alice")

def error_message(linenr, message):
    expected = "%s:%d: manifest error: %s" % (MANIFEST_PATH, linenr, message)
    def check(actual):
        testing.expect.check(expected, actual)
    return check

def injected_script(document):
    scripts = document.findAll("script")
    expected = "<injected script>"
    actual = "<expected content not found>"
    for script in scripts:
        if script["src"] == "injected":
            actual = expected
    testing.expect.check(expected, actual)

script_js = TransferredFile("script.js", """\
function page(method, path, query) {
  writeln("200");
  writeln("Content-Type: text/json");
  writeln();
  writeln("%r", { status: 'ok', method: method, path: path, query: query });
}

function inject(path, query) {
  writeln("script %r", "injected");
}
""")

with frontend.signin("alice"):
    with TransferredFile("MANIFEST", """\
Author = Alice von Testing <alice@example.org>
Description = Extension with invalid MANIFEST

[Page /foo]
Description = Page role with invalid pattern
Script = script.js
Function = page
"""):
        frontend.page(
            "loadmanifest",
            params={ "key": "alice/InvalidExtension" },
            expected_content_type="text/plain",
            expect={ "error_message": error_message(4, "path pattern should not start with a '/'") })

    with script_js, TransferredFile("MANIFEST", """\
Author = Alice von Testing <alice@example.org>
Description = Extension with soon to be missing MANIFEST

[Page foo]
Description = Dummy page role
Script = script.js
Function = page

[Inject tutorial]
Description = Dummy page role
Script = script.js
Function = inject
"""):
        frontend.operation(
            "installextension",
            data={ "extension_name": "InvalidExtension",
                   "author_name": "alice" })

        frontend.operation(
            "foo",
            data={},
            expect={ "method": "POST",
                     "path": "foo" })

        frontend.page(
            "tutorial",
            expect={ "injected_script": injected_script })

    frontend.page(
        "foo",
        expected_http_status=404)

    frontend.page("tutorial")

    frontend.operation(
        "uninstallextension",
        data={ "extension_name": "InvalidExtension",
               "author_name": "alice" })

    with TransferredFile("MANIFEST", """\
Author = Alice von Testing <alice@example.org>
Description = Soon to be inaccessible extension

[Page foo]
Description = Dummy page role
Script = script.js
Function = page
"""):
        frontend.operation(
            "installextension",
            data={ "extension_name": "InvalidExtension",
                   "author_name": "alice" })

        instance.execute(
            ["chmod", "go-rx", "~/CriticExtensions/InvalidExtension"],
            as_user="alice")

        frontend.page(
            "foo",
            expected_http_status=404)

    frontend.operation(
        "uninstallextension",
        data={ "extension_name": "InvalidExtension",
               "author_name": "alice" })
