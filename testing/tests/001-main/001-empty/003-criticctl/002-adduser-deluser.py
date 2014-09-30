# Scenario: Try to add a user 'alice' (already exists).
try:
    instance.criticctl(
        ["adduser",
         "--name", "alice",
         "--email", "alice@example.org",
         "--fullname", "'Alice von Testing'",
         "--password", "testing"])
except testing.CriticctlError as error:
    if "alice: user exists" not in error.stderr.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.stdout)
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Try to delete the user 'nosuchuser' (no such user).
try:
    instance.criticctl(
        ["deluser",
         "--name", "nosuchuser"])
except testing.CriticctlError as error:
    if "nosuchuser: no such user" not in error.stderr.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.stdout)
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Add a user 'extra' and then delete the user again.
try:
    instance.criticctl(
        ["adduser",
         "--name", "extra",
         "--email", "extra@example.org",
         "--fullname", "'Extra von Testing'",
         "--password", "testing"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    instance.registeruser("extra")

    try:
        instance.criticctl(
            ["deluser",
             "--name", "extra"])
    except testing.CriticctlError as error:
        logger.error("correct criticctl usage failed:\n%s"
                     % error.stdout)
