frontend.page(
    "search",
    expect={ "document_title": testing.expect.document_title(u"Review Search"),
             "content_title": testing.expect.paleyellow_title(0, u"Review Search"),
             "pageheader_links": testing.expect.pageheader_links("anonymous"),
             "script_user": testing.expect.script_anonymous_user() })
