with frontend.signin():
    frontend.page("news", expect={ "document_title": testing.expect.document_title(u"News"),
                                   "content_title": testing.expect.paleyellow_title(0, u"News"),
                                   "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                                       "administrator"),
                                   "script_user": testing.expect.script_no_user() })
