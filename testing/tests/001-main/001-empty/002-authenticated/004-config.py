with frontend.signin():
    frontend.page("config", expect={ "document_title": testing.expect.document_title(u"User Preferences"),
                                     "content_title": testing.expect.paleyellow_title(0, u"User Preferences"),
                                     "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                                         "administrator"),
                                     "script_user": testing.expect.script_user("admin") })
