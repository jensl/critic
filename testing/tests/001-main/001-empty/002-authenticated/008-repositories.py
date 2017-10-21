with frontend.signin():
    frontend.page(
        "repositories",
        expect={
            "document_title": testing.expect.document_title("Repositories"),
            "content_title": testing.expect.paleyellow_title(0, "Repositories"),
            "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                "administrator"),
            "script_user": testing.expect.script_user(instance.user("admin"))
        })
