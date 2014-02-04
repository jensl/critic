import re

with_class = testing.expect.with_class
extract_text = testing.expect.extract_text

def extract_addresses(document):
    addresses = []
    for address in document.findAll(attrs=with_class("address")):
        email_id = int(address["data-email-id"])
        selected = "selected" in address["class"].split()
        value = address.find(attrs=with_class("value")).string
        if address.find(attrs=with_class("verified")):
            verified = "verified"
        elif address.find(attrs=with_class("unverified")):
            verified = "unverified"
        else:
            verified = None
        addresses.append((email_id, selected, value, verified))
    return addresses

def emails(expected):
    def check(document):
        actual = [(selected, value, verified)
                  for _, selected, value, verified
                  in extract_addresses(document)]
        testing.expect.check(expected, actual)
    return check

def no_emails(document):
    row = document.find("tr", attrs=with_class("email"))
    testing.expect.check(
        "No email address",
        extract_text(row.find("td", attrs=with_class("value")).find("i")))

ALICE_ID = 2
ALICE_AT_EXAMPLE = "alice@example.org"
ALICE_AT_WONDERLAND = "alice@wonderland.net"
RE_ALICE_AT_WONDERLAND = r"alice@wonderland\.net"

with frontend.signin("alice"):
    # Check initial state.

    frontend.page(
        "home",
        expect={ "addresses": emails([(True, ALICE_AT_EXAMPLE, None)]) })

    # Add another, initially unverified, email address.

    frontend.operation(
        "addemailaddress",
        data={ "subject_id": ALICE_ID,
               "email": "alice@wonderland.net" })

    document = frontend.page(
        "home",
        expect={ "addresses": emails(
                [(True, ALICE_AT_EXAMPLE, None),
                 (False, ALICE_AT_WONDERLAND, "unverified")]) })

    addresses = extract_addresses(document)
    alice_at_example_id = addresses[0][0]
    alice_at_wonderland_id = addresses[1][0]

    # Check that we got a verification mail.

    subject = r"\[Critic\] Please verify your email: " + RE_ALICE_AT_WONDERLAND

    verification_mail = mailbox.pop(
        accept=[testing.mailbox.to_recipient(ALICE_AT_WONDERLAND),
                testing.mailbox.with_subject(subject)],
        timeout=5)

    if not verification_mail:
        testing.expect.check(
            "<verification mail to %s>" % ALICE_AT_WONDERLAND,
            "<no mail received>")

    # Extract the verification link from the verification mail.

    for line in verification_mail.lines:
        match = re.match(
            r"\s+http://[^/]+/verifyemail\?email=([^&]+)&token=([^&]+)", line)
        if match:
            email, token = match.groups()
            testing.expect.check(ALICE_AT_WONDERLAND, email)
            break
    else:
        testing.expect.check(
            "<verification link in verification mail>",
            "<expected content not found>")

    # Request another verification mail.

    frontend.operation(
        "requestverificationemail",
        data={ "email_id": alice_at_wonderland_id })

    verification_mail = mailbox.pop(
        accept=[testing.mailbox.to_recipient(ALICE_AT_WONDERLAND),
                testing.mailbox.with_subject(subject)],
        timeout=5)

    if not verification_mail:
        testing.expect.check(
            "<verification mail to %s>" % ALICE_AT_WONDERLAND,
            "<no mail received>")

    # Verify the new email address.

    response = frontend.page(
        "verifyemail",
        params={ "email": ALICE_AT_WONDERLAND,
                 "token": token },
        disable_redirects=True,
        expected_http_status=307)

    testing.expect.check(
        "/home?email_verified=%d" % alice_at_wonderland_id,
        response.headers["Location"])

    # Check that it's now displayed as verified.

    frontend.page(
        "home",
        params={ "email_verified": str(alice_at_wonderland_id) },
        expect={ "addresses": emails(
                [(True, ALICE_AT_EXAMPLE, None),
                 (False, ALICE_AT_WONDERLAND, "verified")]) })

    # Make the new address the selected one.

    frontend.operation(
        "selectemailaddress",
        data={ "email_id": alice_at_wonderland_id })

    frontend.page(
        "home",
        expect={ "addresses": emails(
                [(False, ALICE_AT_EXAMPLE, None),
                 (True, ALICE_AT_WONDERLAND, "verified")]) })

    # Try to delete the now selected address.

    frontend.operation(
        "deleteemailaddress",
        data={ "email_id": alice_at_wonderland_id },
        expect={ "status": "failure",
                 "code": "notallowed" })

    frontend.page(
        "home",
        expect={ "addresses": emails(
                [(False, ALICE_AT_EXAMPLE, None),
                 (True, ALICE_AT_WONDERLAND, "verified")]) })

    # Delete the other address instead.

    frontend.operation(
        "deleteemailaddress",
        data={ "email_id": alice_at_example_id })

    frontend.page(
        "home",
        expect={ "addresses": emails(
                [(True, ALICE_AT_WONDERLAND, "verified")]) })

    # Now delete the single, selected address.

    frontend.operation(
        "deleteemailaddress",
        data={ "email_id": alice_at_wonderland_id })

    frontend.page(
        "home",
        expect={ "addresses": no_emails })

with frontend.signin():
    # Re-add Alice's original address as the system administrator.

    frontend.operation(
        "addemailaddress",
        data={ "subject_id": ALICE_ID,
               "email": ALICE_AT_EXAMPLE })

    frontend.page(
        "home",
        params={ "user": "alice" },
        expect={ "addresses": emails([(True, ALICE_AT_EXAMPLE, None)]) })
