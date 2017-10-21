with frontend.signin():
    frontend.page(
        "home",
        expect={
            "document_title": testing.expect.document_title("Testing Administrator's Home"),
            "content_title": testing.expect.paleyellow_title(0, "Testing Administrator's Home"),
            "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                "administrator"),
            "script_user": testing.expect.script_user(instance.user("admin"))
        })

with frontend.signin("bob"):
    frontend.operation(
        "changepassword",
        data={ "current_pw": "testing",
               "new_pw": "gnitset" })

frontend.operation(
    "validatelogin",
    data={ "fields": { "username": "bob",
                       "password": "testing" }},
    expect={ "message": "Wrong password" })

with frontend.signin("bob", "gnitset"):
    pass

with frontend.signin():
    frontend.operation(
        "changepassword",
        data={ "subject": "bob",
               "new_pw": "testing" })

with frontend.signin("bob"):
    pass
