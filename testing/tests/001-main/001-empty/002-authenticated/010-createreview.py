with frontend.signin():
    frontend.page("createreview", expect={ "document_title": testing.expect.document_title(u"Create Review"),
                                           "content_title": testing.expect.paleyellow_title(0, u"Create Review"),
                                           "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                                               "administrator"),
                                           "script_user": testing.expect.script_user("admin") })
