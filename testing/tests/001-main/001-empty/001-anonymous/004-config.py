frontend.page(
    "config",
    expect={ "document_title": testing.expect.document_title("User preferences"),
             "content_title": testing.expect.paleyellow_title(0, "User preferences"),
             "pageheader_links": testing.expect.pageheader_links("anonymous"),
             "script_user": testing.expect.script_anonymous_user() })
