# @users alice

ROLES = ["administrator", "developer", "newswriter", "repositories"]

# Scenario: Try to add a role that 'admin' already has.
try:
    output = instance.criticctl(
        ["addrole", "--username", "admin", "--role", "administrator"]
    )
    expected_output = "admin: user already has role 'administrator'"
    if expected_output not in output:
        logger.error("Expected output not found: %r\n%s" % (expected_output, output))
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)

# Scenario: Try to delete a role 'alice' doesn't have.
try:
    output = instance.criticctl(
        ["delrole", "--username", "alice", "--role", "administrator"]
    )
    expected_output = "alice: user does not have role 'administrator'"
    if expected_output not in output:
        logger.error("Expected output not found: %r\n%s" % (expected_output, output))
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)

# Scenario: Try to add a role to a non-existing user.
try:
    instance.criticctl(
        ["addrole", "--username", "nosuchuser", "--role", "administrator"]
    )
except testing.CriticctlError as error:
    if "nosuchuser: no such user" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stdout
        )
else:
    logger.error(
        "incorrect criticctl usage did not fail: " "addrole, non-existing user"
    )

# Scenario: Try to delete a role from a non-existing user.
try:
    instance.criticctl(
        ["delrole", "--username", "nosuchuser", "--role", "administrator"]
    )
except testing.CriticctlError as error:
    if "nosuchuser: no such user" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stdout
        )
else:
    logger.error(
        "incorrect criticctl usage did not fail: " "delrole, non-existing user"
    )

# Scenario: Try to add an invalid role.
try:
    instance.criticctl(["addrole", "--username", "alice", "--role", "joker"])
except testing.CriticctlError as error:
    if "invalid choice: 'joker'" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stderr
        )
else:
    logger.error("incorrect criticctl usage did not fail: " "addrole, invalid role")

# Scenario: Try to delete an invalid role.
try:
    instance.criticctl(["delrole", "--username", "alice", "--role", "joker"])
except testing.CriticctlError as error:
    if "invalid choice: 'joker'" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stderr
        )
else:
    logger.error("incorrect criticctl usage did not fail: " "delrole, invalid role")

# Scenario: Add and then delete each role.
def test_role(role):
    try:
        instance.criticctl(["addrole", "--username", "alice", "--role", role])
    except testing.CriticctlError as error:
        logger.error("correct criticctl usage failed:\n%s" % error.stdout)
    else:
        try:
            instance.criticctl(["delrole", "--username", "alice", "--role", role])
        except testing.CriticctlError as error:
            logger.error("correct criticctl usage failed:\n%s" % error.stdout)


for role in ROLES:
    test_role(role)
