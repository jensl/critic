frontend.page(
    "branches", expect={ "document_title": testing.expect.document_title("Branches"),
                         "content_title": testing.expect.paleyellow_title(0, "Branches"),
                         "pageheader_links": testing.expect.pageheader_links("anonymous"),
                         "script_user": testing.expect.script_no_user() })
