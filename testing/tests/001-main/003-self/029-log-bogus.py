expected = testing.expect.message("'notabranch' doesn't name a branch!", None)
frontend.page(
    url="log",
    params={ "repository": "critic",
             "branch": "notabranch" },
    expect={ "message": expected })


expected = testing.expect.message("Missing URI Parameter!",
                                  "Expected 'repository' parameter.")
frontend.page(
    url="log",
    params={ "branch": "branch_that_does_not_exist" },
    expect={ "message": expected })


expected = testing.expect.message("'nyetvetka' doesn't name a branch!", None)
frontend.page(
    url="log",
    params={ "repository": "critic",
             "branch": "master",
             "base": "nyetvetka" },
    expect={ "message": expected })
