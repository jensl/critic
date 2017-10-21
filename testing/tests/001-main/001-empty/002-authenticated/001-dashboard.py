with frontend.signin():
    frontend.page(
        "dashboard",
        expect={
            "document_title": testing.expect.document_title("Dashboard"),
            "message_title": testing.expect.message_title("No reviews!"),
            "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                "administrator"),
            "script_user": testing.expect.script_user(instance.user("admin"))
        })
