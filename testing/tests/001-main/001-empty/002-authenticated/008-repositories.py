with frontend.signin():
    frontend.page("repositories", expect={ "document_title": testing.expect.document_title(u"Repositories"),
                                           "content_title": testing.expect.paleyellow_title(0, u"Repositories"),
                                           "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                                               "administrator"),
                                           "script_user": testing.expect.script_user("admin") })
