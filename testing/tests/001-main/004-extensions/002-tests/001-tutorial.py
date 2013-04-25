frontend.page("tutorial",
              expect={ "document_title": testing.expect.document_title(u"Tutorials"),
                       "content_title": testing.expect.paleyellow_title(0, u"Tutorials"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                           "extensions"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "extensions" },
              expect={ "document_title": testing.expect.document_title(u"Critic Extensions"),
                       "content_title": testing.expect.paleyellow_title(0, u"Critic Extensions"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                           "extensions"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "extensions-api" },
              expect={ "document_title": testing.expect.document_title(u"Critic Extensions API"),
                       "content_title": testing.expect.paleyellow_title(0, u"Critic Extensions API"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                           "extensions"),
                       "script_user": testing.expect.script_no_user() })
