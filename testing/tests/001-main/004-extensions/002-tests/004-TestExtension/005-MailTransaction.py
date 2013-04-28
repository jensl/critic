mailbox.check_empty()

with frontend.signin("alice"):
    to_alice = testing.mailbox.ToRecipient("alice@example.org")
    to_bob = testing.mailbox.ToRecipient("bob@example.org")

    frontend.operation(
        "MailTransaction",
        data={ "mails": [{ "to": ["alice", "bob"],
                           "subject": "MailTransaction test #1",
                           "body": "This is the mail body.\n\nBye, bye." }] },
        expect={ "message": None })

    def recipients_equal(expected, actual):
        return set(expected) == set(map(str.strip, actual.split(",")))

    def check_mail1(mail):
        testing.expect.check("Alice von Testing <alice@example.org>",
                             mail.header("From"))
        testing.expect.check(["Alice von Testing <alice@example.org>",
                              "Bob von Testing <bob@example.org>"],
                             mail.header("To"), equal=recipients_equal)
        testing.expect.check("MailTransaction test #1",
                             mail.header("Subject"))
        testing.expect.check(["This is the mail body.", "", "Bye, bye."],
                             mail.lines)

    check_mail1(mailbox.pop(to_alice))
    check_mail1(mailbox.pop(to_bob))
