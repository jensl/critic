frontend.page("repositories", expect={ "document_title": testing.expect.document_title("Repositories"),
                                       "content_title": testing.expect.paleyellow_title(0, "Repositories"),
                                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                                       "script_user": testing.expect.script_anonymous_user() })
