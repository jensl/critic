with frontend.signin("alice"):
    frontend.page(
        "extension-resource/TestExtension/helloworld.html",
        expected_content_type="text/html")

    frontend.page(
        "extension-resource/TestExtension/helloworld.css",
        expected_content_type="text/css")

    frontend.page(
        "extension-resource/TestExtension/helloworld.js",
        expected_content_type="text/javascript")

    frontend.page(
        "extension-resource/TestExtension/helloworld.txt",
        expected_http_status=404)
