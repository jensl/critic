frontend.page("dashboard", expect={ "document_title": testing.expect.document_title(u"Dashboard"),
                                    "message_title": testing.expect.message_title(u"No reviews!"),
                                    "pageheader_links": testing.expect.pageheader_links("anonymous"),
                                    "script_user": testing.expect.script_anonymous_user() })
