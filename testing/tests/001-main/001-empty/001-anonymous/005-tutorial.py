frontend.page("tutorial",
              expect={ "document_title": testing.expect.document_title(u"Tutorials"),
                       "content_title": testing.expect.paleyellow_title(0, u"Tutorials"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "request" },
              expect={ "document_title": testing.expect.document_title(u"Requesting a Review"),
                       "content_title": testing.expect.paleyellow_title(0, u"Requesting a Review"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "review" },
              expect={ "document_title": testing.expect.document_title(u"Reviewing Changes"),
                       "content_title": testing.expect.paleyellow_title(0, u"Reviewing Changes"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "filters" },
              expect={ "document_title": testing.expect.document_title(u"Filters"),
                       "content_title": testing.expect.paleyellow_title(0, u"Filters"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "viewer" },
              expect={ "document_title": testing.expect.document_title(u"Repository Viewer"),
                       "content_title": testing.expect.paleyellow_title(0, u"Repository Viewer"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "reconfigure" },
              expect={ "document_title": testing.expect.document_title(u"Reconfiguring Critic"),
                       "content_title": testing.expect.paleyellow_title(0, u"Reconfiguring Critic"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "rebase" },
              expect={ "document_title": testing.expect.document_title(u"Rebasing a Review"),
                       "content_title": testing.expect.paleyellow_title(0, u"Rebasing a Review"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "administration" },
              expect={ "document_title": testing.expect.document_title(u"System Administration"),
                       "content_title": testing.expect.paleyellow_title(0, u"System Administration"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

# Unknown items are ignored and the main Tutorials page is returned instead.
frontend.page("tutorial",
              params={ "item": "nonexisting" },
              expect={ "document_title": testing.expect.document_title(u"Tutorials"),
                       "content_title": testing.expect.paleyellow_title(0, u"Tutorials"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })
