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
                              "mirror": { "remote_url": repository.url,
                                          "remote_branch": "master",
                                          "local_branch": "master" } })

    instance.synchronize_service("branchtracker")
    instance.synchronize_service("branchupdater")

    with repository.workcopy(empty=True) as work:
        REMOTE_URL = instance.repository_url("alice")

        try:
            work.run(
                ["ls-remote", "--exit-code", REMOTE_URL, "refs/heads/master"])
        except testing.repository.GitCommandError:
            logger.error("Repository main branch ('refs/heads/master') "
                         "not fetched as expected.")
            raise testing.TestFailure

    # Check that /repositories still loads correctly now that there's a
    # repository in the system.
    frontend.page(
        "repositories",
        expect={ "document_title": testing.expect.document_title(u"Repositories"),
                 "content_title": testing.expect.paleyellow_title(0, u"Repositories"),
                 "repository": check_repository })

    # Add another repository. This time, without a tracking branch, but we'll
    # actually push the same branch (IOW our current branch of critic.git) to
    # it, simply because we don't really have another available with anything
    # useful in it.
    frontend.operation("addrepository",
                       data={ "name": "other",
                              "path": "other" })

    repository.run(
        ["push", instance.repository_url("alice", repository="other"),
         "HEAD:refs/heads/master"])

    frontend.operation("addrepository",
                       data={ "name": "a" * 65,
                              "path": "validpath2" },
                       expect={ "status": "failure",
                                "code": "paramtoolong:data.name" })

    frontend.operation("addrepository",
                       data={ "name": "",
                              "path": "validpath1" },
                       expect={ "status": "failure",
                                "code": "paramtooshort:data.name" })

    frontend.operation("addrepository",
                       data={ "name": "a/b",
                              "path": "validpath3" },
                       expect={ "status": "failure",
                                "code": "paramcontainsillegalchar:data.name",
                                "message": "invalid input: short name may not contain the character '/'" })

    frontend.operation("addrepository",
                       data={ "name": "critic.git",
                              "path": "validpath3" },
                       expect={ "status": "failure",
                                "code": "badsuffix_name" })

    frontend.operation("addrepository",
                       data={ "name": "r",
                              "path": "validpath" },
                       expect={ "status": "failure",
                                "code": "invalid_name" })

    frontend.operation("addrepository",
                       data={ "name": "validname",
                              "path": "" },
                       expect={ "status": "failure",
                                "code": "paramtooshort:data.path" })
