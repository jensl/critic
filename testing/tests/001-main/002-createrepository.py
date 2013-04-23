import time

with frontend.signin():
    # Check that this URL isn't handled already.  We're using it later to detect
    # that the repository has been created and the tracked branch fetched, and
    # if it's already handled for some reason, that check won't be reliable.
    frontend.page("critic/tested", expected_http_status=404)

    frontend.operation("addrepository",
                       data={ "name": "critic",
                              "path": "critic",
                              "remote": { "url": repository.url,
                                          "branch": "tested" }})

    # If it hasn't happened after 30 seconds, something must be wrong.
    deadline = time.time() + 30
    finished = False

    while not finished and time.time() < deadline:
        # The frontend.page() function returns None if the HTTP status was
        # 404, and a BeautifulSoup object if it was 200.
        if frontend.page("critic/tested", expected_http_status=[200, 404]) is None:
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
        logger.error("Repository main branch ('refs/heads/tested') not fetched after 30 seconds.")
        raise testing.TestFailure
