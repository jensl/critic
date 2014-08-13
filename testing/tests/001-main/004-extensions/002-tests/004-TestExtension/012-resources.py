with frontend.signin("alice"):
    frontend.page(
        "extension-resource/TestExtension/helloworld.html",
        expected_content_type="text/html")

    frontend.page(
        "extension-resource/TestExtension/helloworld.css",
        expected_content_type="text/css")

    # This resource has an extra period in its name, the check that this doesn't
    # interfere with the content type guessing.
    frontend.page(
        "extension-resource/TestExtension/hello.world.js",
        expected_content_type="text/javascript")

    frontend.page(
        "extension-resource/TestExtension/helloworld.txt",
        expected_http_status=404)
