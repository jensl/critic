frontend.page("tutorial",
              expect={ "document_title": testing.expect.document_title("Tutorials"),
                       "content_title": testing.expect.paleyellow_title(0, "Tutorials"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "request" },
              expect={ "document_title": testing.expect.document_title("Requesting a Review"),
                       "content_title": testing.expect.paleyellow_title(0, "Requesting a Review"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "review" },
              expect={ "document_title": testing.expect.document_title("Reviewing Changes"),
                       "content_title": testing.expect.paleyellow_title(0, "Reviewing Changes"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "filters" },
              expect={ "document_title": testing.expect.document_title("Filters"),
                       "content_title": testing.expect.paleyellow_title(0, "Filters"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "archival" },
              expect={ "document_title": testing.expect.document_title("Review branch archival"),
                       "content_title": testing.expect.paleyellow_title(0, "Review branch archival"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "viewer" },
              expect={ "document_title": testing.expect.document_title("Repository Viewer"),
                       "content_title": testing.expect.paleyellow_title(0, "Repository Viewer"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "reconfigure" },
              expect={ "document_title": testing.expect.document_title("Reconfiguring Critic"),
                       "content_title": testing.expect.paleyellow_title(0, "Reconfiguring Critic"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "rebase" },
              expect={ "document_title": testing.expect.document_title("Rebasing a Review"),
                       "content_title": testing.expect.paleyellow_title(0, "Rebasing a Review"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "administration" },
              expect={ "document_title": testing.expect.document_title("System Administration"),
                       "content_title": testing.expect.paleyellow_title(0, "System Administration"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "customization" },
              expect={ "document_title": testing.expect.document_title("System Customization"),
                       "content_title": testing.expect.paleyellow_title(0, "System Customization"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

frontend.page("tutorial",
              params={ "item": "search" },
              expect={ "document_title": testing.expect.document_title("Review Quick Search"),
                       "content_title": testing.expect.paleyellow_title(0, "Review Quick Search"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })

# Unknown items are ignored and the main Tutorials page is returned instead.
frontend.page("tutorial",
              params={ "item": "nonexisting" },
              expect={ "document_title": testing.expect.document_title("Tutorials"),
                       "content_title": testing.expect.paleyellow_title(0, "Tutorials"),
                       "pageheader_links": testing.expect.pageheader_links("anonymous"),
                       "script_user": testing.expect.script_no_user() })
