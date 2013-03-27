with frontend.signin():
    frontend.page("home", expect={ "document_title": testing.expect.document_title(u"Testing Administrator's Home"),
                                   "content_title": testing.expect.paleyellow_title(0, u"Testing Administrator's Home"),
                                   "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                                       "administrator"),
                                   "script_user": testing.expect.script_user("admin") })
