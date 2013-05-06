ROLES = ["administrator", "developer", "newswriter", "repositories"]

# Scenario: Try to add a role that 'admin' already has.
try:
    output = instance.execute(
        ["sudo", "criticctl", "addrole",
         "--name", "admin",
         "--role", "administrator"])
    expected_output = "admin: user already has role 'administrator'"
    if expected_output not in output.splitlines():
        logger.error("Expected output not found: %r\n%s"
                     % (expected_output, output))
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.output)

# Scenario: Try to delete a role 'alice' doesn't have.
try:
    output = instance.execute(
        ["sudo", "criticctl", "delrole",
         "--name", "alice",
         "--role", "administrator"])
    expected_output = "alice: user doesn't have role 'administrator'"
    if expected_output not in output.splitlines():
        logger.error("Expected output not found: %r\n%s"
                     % (expected_output, output))
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.output)

# Scenario: Try to add a role to a non-existing user.
try:
    instance.execute(
        ["sudo", "criticctl", "addrole",
         "--name", "nosuchuser",
         "--role", "administrator"])
except testing.virtualbox.GuestCommandError as error:
    if "nosuchuser: no such user" not in error.output.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.output)
else:
    logger.error("incorrect criticctl usage did not fail: "
                 "addrole, non-existing user")

# Scenario: Try to delete a role from a non-existing user.
try:
    instance.execute(
        ["sudo", "criticctl", "delrole",
         "--name", "nosuchuser",
         "--role", "administrator"])
except testing.virtualbox.GuestCommandError as error:
    if "nosuchuser: no such user" not in error.output.splitlines():
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.output)
else:
    logger.error("incorrect criticctl usage did not fail: "
                 "delrole, non-existing user")

# Scenario: Try to add an invalid role.
try:
    instance.execute(
        ["sudo", "criticctl", "addrole",
         "--name", "alice",
         "--role", "joker"])
except testing.virtualbox.GuestCommandError as error:
    if "invalid choice: 'joker'" not in error.output:
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.output)
else:
    logger.error("incorrect criticctl usage did not fail: "
                 "addrole, invalid role")

# Scenario: Try to delete an invalid role.
try:
    instance.execute(
        ["sudo", "criticctl", "delrole",
         "--name", "alice",
         "--role", "joker"])
except testing.virtualbox.GuestCommandError as error:
    if "invalid choice: 'joker'" not in error.output:
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.output)
else:
    logger.error("incorrect criticctl usage did not fail: "
                 "delrole, invalid role")

# Scenario: Add and then delete each role.
def test_role(role):
    try:
        instance.execute(
            ["sudo", "criticctl", "addrole",
             "--name", "alice",
             "--role", role])
    except testing.virtualbox.GuestCommandError as error:
        logger.error("correct criticctl usage failed:\n%s"
                     % error.output)
    else:
        try:
            instance.execute(
                ["sudo", "criticctl", "delrole",
                 "--name", "alice",
                 "--role", role])
        except testing.virtualbox.GuestCommandError as error:
            logger.error("correct criticctl usage failed:\n%s"
                         % error.output)
for role in ROLES:
    test_role(role)
