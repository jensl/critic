frontend.page(
    "manageextensions",
    expect={ "document_title": testing.expect.document_title("Manage Extensions"),
             "content_title": testing.expect.paleyellow_title(0, "Available Extensions"),
             "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                 "extensions"),
             "script_user": testing.expect.script_anonymous_user() })

frontend.page(
    "manageextensions",
    params={ "what": "available" },
    expect={ "document_title": testing.expect.document_title("Manage Extensions"),
             "content_title": testing.expect.paleyellow_title(0, "Available Extensions"),
             "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                 "extensions"),
             "script_user": testing.expect.script_anonymous_user() })

frontend.page(
    "manageextensions",
    params={ "what": "installed" },
    expect={ "document_title": testing.expect.document_title("Manage Extensions"),
             "content_title": testing.expect.paleyellow_title(0, "Installed Extensions"),
             "pageheader_links": testing.expect.pageheader_links("anonymous",
                                                                 "extensions"),
             "script_user": testing.expect.script_anonymous_user() })
