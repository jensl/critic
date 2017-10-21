import os

with_class = testing.expect.with_class
extract_text = testing.expect.extract_text

def check_echo_filter_type(document):
    filterdialog = document.find("div", attrs=with_class("filterdialog"))
    type_select = filterdialog.find("select", attrs={ "name": "type" })
    type_options = type_select.findAll("option")

    testing.expect.check(4, len(type_options))
    testing.expect.check("echo", extract_text(type_options[-1]))
    testing.expect.check("extensionhook", type_options[-1]["value"])
    testing.expect.check("echo", type_options[-1]["data-filterhook-name"])

    try:
        int(type_options[-1]["data-extension-id"])
    except (KeyError, ValueError):
        testing.logger.error("invalid or missing data-extension-id attribute")

def check_echo_filter(filter_id):
    def check(document):
        filters = document.find("table", attrs=with_class("filters"))
        for tr in filters.findAll("tr"):
            path_td = tr.find("td", attrs=with_class("path"))
            if not path_td or extract_text(path_td) != "015-filterhook/include/":
                continue
            title_td = tr.find("td", attrs=with_class("title"))
            testing.expect.check("echo", extract_text(title_td))
            data_td = tr.find("td", attrs=with_class("data"))
            testing.expect.check("this is the data", extract_text(data_td))
            break
        else:
            testing.logger.error("echo extension hook filter not found")

    return check

with frontend.signin("alice"):
    frontend.page(
        "home",
        expect={ "check echo filter type": check_echo_filter_type })

    result = frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/TestExtension",
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "015-filterhook/include/",
               "data": "this is the data" })

    filter_id = result["filter_id"]

    frontend.page(
        "home",
        expect={ "check echo filter": check_echo_filter(filter_id) })

with repository.workcopy() as work:
    work.run(["checkout", "-b", "r/015-filterhook"])

    include = os.path.join(work.path, "015-filterhook", "include")
    exclude = os.path.join(work.path, "015-filterhook", "exclude")

    os.makedirs(include)
    os.makedirs(exclude)

    def make(directory, filename):
        with open(os.path.join(directory, filename), "w") as file:
            print(filename, file=file)

    make(include, "file1")
    make(include, "file2")
    make(exclude, "file3")

    work.run(["add", "015-filterhook"])
    work.run(["commit", "-mFirst"])

    review_id = testing.utils.createReviewViaPush(work, "alice")

    instance.synchronize_service("extensiontasks")
    instance.synchronize_service("maildelivery")

    # Ignore this mail; not very interesting in this context.
    mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("New Review: First")])

    to_alice = mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("filterhook.js::filterhook")])

    testing.expect.check(
        ['data: "this is the data"',
         'review.id: %d' % review_id,
         'user.name: alice',
         'commits: ["First\\n"]',
         'files: ["015-filterhook/include/file1","015-filterhook/include/file2"]'],
        to_alice.lines)

    mailbox.check_empty()

    make(exclude, "file4")

    work.run(["add", "015-filterhook"])
    work.run(["commit", "-mSecond"])

    make(include, "file5")
    make(include, "file6")

    work.run(["add", "015-filterhook"])
    work.run(["commit", "-mThird"])

    work.run(["push", "bob@%s:/var/git/critic.git" % instance.hostname,
              "HEAD"])

    instance.synchronize_service("extensiontasks")
    instance.synchronize_service("maildelivery")

    # Ignore this mail; not very interesting in this context.
    mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("Updated Review: First")])

    to_alice = mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("filterhook.js::filterhook")])

    testing.expect.check(
        ['data: "this is the data"',
         'review.id: %d' % review_id,
         'user.name: bob',
         'commits: ["Third\\n","Second\\n"]',
         'files: ["015-filterhook/include/file5","015-filterhook/include/file6"]'],
        to_alice.lines)

    mailbox.check_empty()

    make(include, "explode")

    work.run(["add", "015-filterhook"])
    work.run(["commit", "-mExplode"])

    explode_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    work.run(["push", "bob@%s:/var/git/critic.git" % instance.hostname,
              "HEAD"])

    instance.synchronize_service("extensiontasks")
    instance.synchronize_service("maildelivery")

    # Ignore this mail; not very interesting in this context.
    mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("Updated Review: First")])

    to_alice = mailbox.pop(
        [testing.mailbox.ToRecipient("alice@example.org"),
         testing.mailbox.WithSubject("Failed: echo")])

    testing.expect.check(
         ['An error occurred while processing an extension hook filter event!',
          '',
          'Filter details:',
          '',
          '  Extension:   TestExtension hosted by Alice von Testing',
          '  Filter hook: echo',
          '  Repository:  critic',
          '  Path:        015-filterhook/include/',
          '  Data:        "this is the data"',
          '',
          'Event details:',
          '',
          '  Review:  r/%d "First"' % review_id,
          '  Commits: %s "Explode"' % explode_sha1[:8],
          '',
          'Error details:',
          '',
          '  Error:  Process returned non-zero exit status 1',
          '  Output:',
          '',
          "    Failed to call 'filterhook.js::filterhook()':",
          '      Error: Boom!',
          '        Error: Boom!',
          '            at filterhook.js:9:15',
          '            at filterhook (filterhook.js:6:9)',
          '',
          '-- critic'],
         to_alice.lines)

    mailbox.check_empty()

with frontend.signin("bob"):
    frontend.operation(
        "deleteextensionhookfilter",
        data={ "subject": "bob",
               "filter_id": filter_id },
        expect={ "status": "failure",
                 "message": ("Filter to delete does not exist "
                             "or belongs to another user!") })

    frontend.operation(
        "deleteextensionhookfilter",
        data={ "subject": "alice",
               "filter_id": filter_id },
        expect={ "status": "failure",
                 "message": ("Operation not permitted, user "
                             "that lacks role 'administrator'.") })

with frontend.signin("admin"):
    frontend.operation(
        "deleteextensionhookfilter",
        data={ "subject": "alice",
               "filter_id": filter_id })

    result = frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/TestExtension",
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "015-filterhook/include/",
               "data": "this is the data" })

    filter_id = result["filter_id"]

with frontend.signin("alice"):
    result = frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/TestExtension",
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "015-filterhook/include/",
               "data": "this is the data",
               "replaced_filter_id": filter_id })

    filter_id = result["filter_id"]

    frontend.operation(
        "deleteextensionhookfilter",
        data={ "subject": "alice",
               "filter_id": filter_id })

    frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/TestExtension",
               "repository": "critic",
               "filterhook_name": "explode",
               "path": "/" },
        expect={ "status": "failure",
                 "code": "invalidrequest",
                 "message": ("The extension doesn't have a filter "
                             "hook role named 'explode'!") })

    frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/WrongExtension",
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "/" },
        expect={ "status": "failure",
                 "code": "invalidextension",
                 "message": ("Invalid or inaccessible extension dir: "
                             "/home/alice/CriticExtensions/WrongExtension") })

    frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": 4711,
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "/" },
        expect={ "status": "failure",
                 "code": "invalidextension",
                 "message": "Invalid extension id: 4711" })

    frontend.operation(
        "uninstallextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })

    frontend.operation(
        "addextensionhookfilter",
        data={ "subject": "alice",
               "extension": "alice/TestExtension",
               "repository": "critic",
               "filterhook_name": "echo",
               "path": "/" },
        expect={ "status": "failure",
                 "code": "invalidrequest",
                 "message": ("The extension \"TestExtension hosted by Alice "
                             "von Testing\" must be installed first!") })

    frontend.operation(
        "installextension",
        data={ "author_name": "alice",
               "extension_name": "TestExtension" })
