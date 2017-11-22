import time

with frontend.signin():
    instance.register_repository(
        frontend.json(
            "repositories",
            post={
                "name": "critic",
                "path": "critic.git",
                "mirror": {
                    "url": repository.url(),
                    "branches": [{"remote_name": "master"}],
                },
            },
            expect={
                "id": int,
                "name": "critic",
                "path": "critic.git",
                "urls": [str],
                "documentation_path": None,
            },
        )
    )

    instance.synchronize_service(
        # Creates ('git init') the repository.
        "maintenance",
        # Pushes the master branch to the repository.
        "branchtracker",
        # Processes the push.
        "branchupdater",
    )

    REMOTE_URL = instance.repository_url("alice")

    try:
        repository.run(["ls-remote", "--exit-code", REMOTE_URL, "refs/heads/master"])
    except testing.repository.GitCommandError:
        logger.error(
            "Repository main branch ('refs/heads/master') " "not fetched as expected."
        )
        raise testing.TestFailure

    # frontend.operation("addrepository",
    #                    data={ "name": "a" * 65,
    #                           "path": "validpath2" },
    #                    expect={ "status": "failure",
    #                             "code": "paramtoolong:data.name" })

    # frontend.operation("addrepository",
    #                    data={ "name": "",
    #                           "path": "validpath1" },
    #                    expect={ "status": "failure",
    #                             "code": "paramtooshort:data.name" })

    # frontend.operation("addrepository",
    #                    data={ "name": "a/b",
    #                           "path": "validpath3" },
    #                    expect={ "status": "failure",
    #                             "code": "paramcontainsillegalchar:data.name",
    #                             "message": "invalid input: short name may not contain the character '/'" })

    # frontend.operation("addrepository",
    #                    data={ "name": "critic.git",
    #                           "path": "validpath3" },
    #                    expect={ "status": "failure",
    #                             "code": "badsuffix_name" })

    # frontend.operation("addrepository",
    #                    data={ "name": "r",
    #                           "path": "validpath" },
    #                    expect={ "status": "failure",
    #                             "code": "invalid_name" })

    # frontend.operation("addrepository",
    #                    data={ "name": "validname",
    #                           "path": "" },
    #                    expect={ "status": "failure",
    #                             "code": "paramtooshort:data.path" })

    # frontend.operation("addrepository",
    #                    data={ "name": "chromium",
    #                           "path": "chromium" })
