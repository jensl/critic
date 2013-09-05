# Scenario: /showtree or /showfile loaded, with or without a repository
# specifier, with a SHA-1 that is or is not present in that/any repository, or a
# path that is or is not valid.

VALID_SHA1 = "378a00935735431d5408dc8acbca77e6887f91c6"
INVALID_SHA1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

VALID_TREE_PATH = "src/page"
INVALID_TREE_PATH = "src/horse"

VALID_FILE_PATH = "src/page/showtree.py"
INVALID_FILE_PATH = "src/page/showpuppy.py"

missing_sha1 = testing.expect.message(
    expected_title="SHA-1 not found",
    expected_body="Couldn't find commit %s in any repository." % INVALID_SHA1)

missing_tree = testing.expect.message(
    expected_title="Directory does not exist",
    expected_body=("There is no directory named /%s in the commit %s."
                   % (INVALID_TREE_PATH, VALID_SHA1[:8])))

missing_file = testing.expect.message(
    expected_title="File does not exist",
    expected_body=("There is no file named /%s in the commit %s."
                   % (INVALID_FILE_PATH, VALID_SHA1[:8])))

frontend.page(
    "showtree",
    params={ "sha1": VALID_SHA1,
             "path": VALID_TREE_PATH },
    expect={ "message": testing.expect.no_message() })

frontend.page(
    "showtree",
    params={ "sha1": INVALID_SHA1,
             "path": VALID_TREE_PATH },
    expect={ "message": missing_sha1 })

frontend.page(
    "showtree",
    params={ "sha1": VALID_SHA1,
             "path": INVALID_TREE_PATH },
    expect={ "message": missing_tree })

frontend.page(
    "showfile",
    params={ "sha1": VALID_SHA1,
             "path": VALID_FILE_PATH },
    expect={ "message": testing.expect.no_message() })

frontend.page(
    "showfile",
    params={ "sha1": INVALID_SHA1,
             "path": VALID_FILE_PATH },
    expect={ "message": missing_sha1 })

frontend.page(
    "showfile",
    params={ "sha1": VALID_SHA1,
             "path": INVALID_FILE_PATH },
    expect={ "message": missing_file })
