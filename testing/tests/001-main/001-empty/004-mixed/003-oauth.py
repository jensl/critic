import re
import urllib
import urlparse

def externalauthURL(name):
    return "externalauth/%s?%s" % (name, urllib.urlencode({ "target": "/" }))

with_class = testing.expect.with_class

def isprefix(expected, actual):
    return actual.startswith(expected)
def issuffix(expected, actual):
    return actual.endswith(expected)

def expect_admin_mail(subject):
    admin_mail = mailbox.pop(
        testing.mailbox.to_recipient("admin@example.org"), timeout=5)

    if not admin_mail:
        testing.expect.check("<admin mail>", "<no admin mail received>")

    testing.expect.check(subject, admin_mail.headers["subject"][0]["value"])

def start_externalauth(name):
    response = frontend.page(
        externalauthURL(name),
        disable_redirects=True,
        expected_http_status=302)

    redirect_url = response.headers["Location"]

    testing.expect.check("https://example.com/authorize?",
                         redirect_url,
                         equal=isprefix)

    parsed_url = urlparse.urlparse(redirect_url)
    parsed_query = urlparse.parse_qs(parsed_url.query)
    state = parsed_query.get("state", ["no state received"])[0]

    if state == "no state received":
        testing.expect.check("<state parameter in authorize URI query>",
                             "<no state parameter: %r>" % parsed_url.query)

    return state

def finish_externalauth(name, state):
    response = frontend.page(
        "oauth/" + name,
        params={ "state": state,
                 "code": "correct" },
        disable_redirects=True,
        expected_http_status=302)

    return response.headers["Location"]

# Check that all the expected links to external providers are present
# on the "Sign in" page.

NAMES = ["alice", "carol", "felix", "gina"]

def oauth_links(document):
    providers = document.findAll("div", attrs=with_class("provider"))
    names = set(NAMES)
    expected_text = "Sign in using your "
    for provider in providers:
        testing.expect.check(expected_text, provider.contents[0])
        expected_text = "or "

        link = provider.find("a")
        words = link.string.split()
        testing.expect.check(2, len(words))
        testing.expect.check("account", words[-1], equal=issuffix)

        name = words[0].lower()
        if name in names:
            testing.expect.check("/" + externalauthURL(name), link["href"])
            names.remove(name)
        else:
            testing.logger.error("Unexpected provider: %r" % name)

    if names:
        testing.expect.check("<link to providers: %r>" % names,
                             "<no links found>")

frontend.page(
    "login",
    expect={ "oauth links": oauth_links })

#
# Try to sign in using the 'alice' provider, then connect alice's
# account manually, and try again.  Make some mistakes along the way.
#

state = start_externalauth("alice")

# Try with the wrong state.
frontend.page(
    "oauth/alice",
    params={ "state": "not the right state",
             "code": "irrelevant" },
    expect={ "message": testing.expect.message("Authentication failed",
                                               "Invalid OAuth state",
                                               body_equal=re.search) })
expect_admin_mail(
    "wsgi: InvalidRequest: Invalid OAuth state: not the right state")

# Try with the wrong code (the right code is always "correct".)
frontend.page(
    "oauth/alice",
    params={ "state": state,
             "code": "incorrect" },
    expect={ "message": testing.expect.message("Authentication failed",
                                               "Incorrect code",
                                               body_equal=re.search) })
expect_admin_mail("wsgi: Failure: Incorrect code")

redirect_url = finish_externalauth("alice", state)
message_check = testing.expect.message("User registration not enabled", None)

frontend.page(
    redirect_url,
    expect={ "message": message_check })

# Connect the account manually.
instance.execute(["sudo", "criticctl", "connect",
                  "--name", "alice",
                  "--provider", "alice",
                  "--account", "account-alice"])

# Sign in for real now.
state = start_externalauth("alice")

with frontend.signin(username=None):
    redirect_url = finish_externalauth("alice", state)
    testing.expect.check("/", redirect_url)

    if not frontend.session_id:
        testing.expect.check("<signed in after /oauth/alice>",
                             "<no session cookie set>")

    document_title_check = testing.expect.document_title(
        "Alice von Testing's Home")

    frontend.page(
        "home",
        expect={ "document title": document_title_check })

#
# Create user 'carol' by signing in using the 'carol' provider.
#

state = start_externalauth("carol")
redirect_url = finish_externalauth("carol", state)

testing.expect.check("/createuser?",
                     redirect_url,
                     equal=isprefix)

parsed_url = urlparse.urlparse(redirect_url)
parsed_query = urlparse.parse_qs(parsed_url.query)

testing.expect.check(["carol"], parsed_query.get("provider"))
testing.expect.check(["account-carol"], parsed_query.get("account"))
testing.expect.check(1, len(parsed_query.get("token")))
testing.expect.check(["/"], parsed_query.get("target"))
testing.expect.check(["carol"], parsed_query.get("username"))
testing.expect.check(["carol@example.org"], parsed_query.get("email"))
testing.expect.check(["Carol von Testing"], parsed_query.get("fullname"))

token = parsed_query.get("token")[0]

# Try with wrong account name.
frontend.operation(
    "registeruser",
    data={ "username": "carol",
           "fullname": "Carol von Testing",
           "email": "carol@example.org",
           "external": { "provider": "carol",
                         "account": "wrong-carol",
                         "token": token }},
    expect={ "message": "Invalid external authentication state." })

# Try with wrong token.
frontend.operation(
    "registeruser",
    data={ "username": "carol",
           "fullname": "Carol von Testing",
           "email": "carol@example.org",
           "external": { "provider": "carol",
                         "account": "account-carol",
                         "token": "wrong token" }},
    expect={ "message": "Invalid external authentication state." })

with frontend.signin(username=None):
    # Use right account and token.  This should leave us signed in as carol.
    frontend.operation(
        "registeruser",
        data={ "username": "carol",
               "fullname": "Carol von Testing",
               "email": "carol@example.org",
               "external": { "provider": "carol",
                             "account": "account-carol",
                             "token": token }})

    if not frontend.session_id:
        testing.expect.check("<signed in after /registeruser>",
                             "<no session cookie set>")

    # Check that the email address isn't unverified.
    def email_not_unverified(document):
        address = document.find(attrs=with_class("address"))
        if address.find(attrs=with_class("unverified")):
            testing.expect.check("<carol's email is not unverified>",
                                 "<carol's email is unverified>")

    document_title_check = testing.expect.document_title(
        "Carol von Testing's Home")

    frontend.page(
        "home",
        expect={ "document title": document_title_check,
                 "email not unverified": email_not_unverified })

    expect_admin_mail("wsgi[registeruser]: User 'carol' registered")

#
# Create user 'felix' by signin in using the 'felix' provider, which
# has 'bypass_createuser' set, so this will be quick.
#

state = start_externalauth("felix")

with frontend.signin(username=None):
    redirect_url = finish_externalauth("felix", state)

    if not frontend.session_id:
        testing.expect.check("<signed in after /oauth/felix>",
                             "<no session cookie set>")

    document_title_check = testing.expect.document_title(
        "Felix von Testing's Home")

    frontend.page(
        "home",
        expect={ "document title": document_title_check,
                 "email not unverified": email_not_unverified })

    expect_admin_mail("wsgi[oauth/felix]: User 'felix' registered")

#
# Create user 'gina' by signin in using the 'gina' provider, which
# has 'verify_email_addresses' set.
#

state = start_externalauth("gina")
redirect_url = finish_externalauth("gina", state)

testing.expect.check("/createuser?",
                     redirect_url,
                     equal=isprefix)

parsed_url = urlparse.urlparse(redirect_url)
parsed_query = urlparse.parse_qs(parsed_url.query)
token = parsed_query.get("token")[0]

with frontend.signin(username=None):
    # Use right account and token.  This should leave us signed in as carol.
    frontend.operation(
        "registeruser",
        data={ "username": "gina",
               "fullname": "Gina von Testing",
               "email": "gina@example.org",
               "external": { "provider": "gina",
                             "account": "account-gina",
                             "token": token }})

    if not frontend.session_id:
        testing.expect.check("<signed in after /registeruser>",
                             "<no session cookie set>")

    # Check that the email address isn't unverified.
    def email_unverified(document):
        address = document.find(attrs=with_class("address"))
        if not address.find(attrs=with_class("unverified")):
            testing.expect.check("<carol's email unverified>",
                                 "<carol's email is not unverified>")

    document_title_check = testing.expect.document_title(
        "Gina von Testing's Home")

    frontend.page(
        "home",
        expect={ "document title": document_title_check,
                 "email unverified": email_unverified })

    expect_admin_mail("wsgi[registeruser]: User 'gina' registered")

    subject = r"\[Critic\] Please verify your email: gina@example\.org"

    verification_mail = mailbox.pop(
        accept=[testing.mailbox.to_recipient("gina@example.org"),
                testing.mailbox.with_subject(subject)],
        timeout=5)

    if not verification_mail:
        testing.expect.check(
            "<verification mail to gina@example.org>",
            "<no mail received>")
