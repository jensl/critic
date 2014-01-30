# Scenario: Try to add a user 'alice' (already exists).
try:
    instance.execute(
        ["sudo", "criticctl", "adduser",
         "--name", "alice",
         "--email", "alice@example.org",
         "--fullname", "'Alice von Testing'",
         "--password", "testing"])
except testing.virtualbox.GuestCommandError as error:
    if "alice: user exists" not in error.stdout.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.stdout)
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Try to delete the user 'nosuchuser' (no such user).
try:
    instance.execute(
        ["sudo", "criticctl", "deluser",
         "--name", "nosuchuser"])
except testing.virtualbox.GuestCommandError as error:
    if "nosuchuser: no such user" not in error.stdout.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.stdout)
else:
    logger.error("incorrect criticctl usage did not fail")

# Scenario: Add a user 'extra' and then delete the user again.
try:
    instance.execute(
        ["sudo", "criticctl", "adduser",
         "--name", "extra",
         "--email", "extra@example.org",
         "--fullname", "'Extra von Testing'",
         "--password", "testing"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    try:
        instance.execute(
            ["sudo", "criticctl", "deluser",
             "--name", "extra"])
    except testing.virtualbox.GuestCommandError as error:
        logger.error("correct criticctl usage failed:\n%s"
                     % error.stdout)
