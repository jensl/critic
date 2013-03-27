# Note: /createreview redirects to /login for anonymous users.
frontend.page("createreview", expect={ "document_title": testing.expect.document_title(u"Sign in"),
                                       "content_title": testing.expect.paleyellow_title(0, u"Sign in"),
                                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                                       "script_user": testing.expect.script_no_user() })
