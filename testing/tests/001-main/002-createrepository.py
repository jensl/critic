import time

def check_repository(document):
    rows = document.findAll("tr", attrs=testing.expect.with_class("repository"))
    testing.expect.check(1, len(rows))

    def check_cell(row, class_name, expected_string, inline_element_type=None):
        cells = row.findAll("td", attrs=testing.expect.with_class(class_name))
        testing.expect.check(1, len(cells))
        if inline_element_type:
            testing.expect.check(1, len(cells[0].findAll(inline_element_type)))
            string = cells[0].findAll("i")[0].string
        else:
            string = cells[0].string
        if string is None:
            string = ""
        testing.expect.check(expected_string, string)

    check_cell(rows[0], "name", "critic")
    check_cell(rows[0], "location", "http://%s/critic.git" % instance.hostname)
    check_cell(rows[0], "upstream", "&nbsp;")

    rows = document.findAll("tr", attrs=testing.expect.with_class("details"))
    testing.expect.check(1, len(rows))

    tables = rows[0].findAll("table", attrs=testing.expect.with_class("trackedbranches"))
    testing.expect.check(1, len(tables))

    # Would like to use 'tables[0].findAll()' here, but BeautifulSoup apparently
    # doesn't parse nested tables correctly, so these rows aren't actually part
    # of the 'trackedbranches' table according to it.
    rows = document.findAll("tr", attrs=testing.expect.with_class("branch"))
    testing.expect.check(2, len(rows))

    check_cell(rows[0], "localname", "Tags", inline_element_type="i")
    check_cell(rows[0], "remote", repository.url)
    check_cell(rows[0], "remotename", "N/A", inline_element_type="i")
    check_cell(rows[0], "enabled", "Yes")
    check_cell(rows[0], "users", "")

    check_cell(rows[1], "localname", "master")
    check_cell(rows[1], "remote", repository.url)
    check_cell(rows[1], "remotename", "master")
    check_cell(rows[1], "enabled", "Yes")
    check_cell(rows[1], "users", "")

with frontend.signin():
    # Check that this URL isn't handled already.  We're using it later to detect
    # that the repository has been created and the tracked branch fetched, and
    # if it's already handled for some reason, that check won't be reliable.
    frontend.page("critic/master", expected_http_status=404)

    frontend.operation("addrepository",
                       data={ "name": "critic",
                              "path": "critic",
                              "remote": { "url": repository.url,
                                          "branch": "master" }})

    # If it hasn't happened after 30 seconds, something must be wrong.
    deadline = time.time() + 30
    finished = False

    while not finished and time.time() < deadline:
        # The frontend.page() function returns None if the HTTP status was
        # 404, and a BeautifulSoup object if it was 200.
        if frontend.page("critic/master", expected_http_status=[200, 404]) is None:
            time.sleep(0.5)
            while True:
                mail = mailbox.pop(accept=testing.mailbox.with_subject("^branchtracker.log: "))
                if not mail:
                    break
                logger.error("Administrator message: %s\n > %s"
                             % (mail.header("Subject"), "\n > ".join(mail.lines)))
                raise testing.TestFailure
        else:
            finished = True

    if not finished:
        logger.error("Repository main branch ('refs/heads/master') not fetched after 30 seconds.")
        raise testing.TestFailure

    # Check that /repositories still loads correctly now that there's a
    # repository in the system.
    frontend.page(
        "repositories",
        expect={ "document_title": testing.expect.document_title(u"Repositories"),
                 "content_title": testing.expect.paleyellow_title(0, u"Repositories"),
                 "repository": check_repository })

    frontend.operation("addrepository",
                       data={ "name": "a" * 65,
                              "path": "validpath2" },
                       expect={ "status": "failure",
                                "code": "paramtoolong_name" })

    frontend.operation("addrepository",
                       data={ "name": "",
                              "path": "validpath1" },
                       expect={ "status": "failure",
                                "code": "paramtooshort_name" })

    frontend.operation("addrepository",
                       data={ "name": "a/b",
                              "path": "validpath3" },
                       expect={ "status": "failure",
                                "code": "paramcontainsillegalchar_name" })
