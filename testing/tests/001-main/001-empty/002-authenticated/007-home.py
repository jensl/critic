with frontend.signin():
    frontend.page(
        "home",
        expect={ "document_title": testing.expect.document_title(u"Testing Administrator's Home"),
                 "content_title": testing.expect.paleyellow_title(0, u"Testing Administrator's Home"),
                 "pageheader_links": testing.expect.pageheader_links("authenticated",
                                                                     "administrator"),
                 "script_user": testing.expect.script_user("admin") })

with frontend.signin("bob"):
    frontend.operation(
        "changepassword",
        data={ "current_pw": "testing",
               "new_pw": "gnitset" })

try:
    frontend.operation(
        "validatelogin",
        data={ "username": "bob",
               "password": "testing" },
        expect={ "message": "Wrong password!" })
except testing.TestFailure:
    # Make sure we don't accidentally stay signed in.
    frontend.signout()

with frontend.signin("bob", "gnitset"):
    pass

with frontend.signin():
    frontend.operation(
        "changepassword",
        data={ "subject": "bob",
               "new_pw": "testing" })

with frontend.signin("bob"):
    pass
