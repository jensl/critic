# Scenario: Invalid format.
try:
    instance.execute(
        ["sudo", "criticctl", "listusers", "--format", "oranges"])
except testing.virtualbox.GuestCommandError as error:
    if "invalid choice: 'oranges'" not in error.stderr:
        logger.error("criticctl failed with unexpected error message:\n%s"
                     % error.stderr)
else:
    logger.error("incorrect criticctl usage did not fail")

expected = """\
  id |    name    |              email             |            fullname            | status
-----+------------+--------------------------------+--------------------------------+--------
   1 |      admin |              admin@example.org | Testing Administrator          | current
   2 |      alice |              alice@example.org | Alice von Testing              | current
   3 |        bob |                bob@example.org | Bob von Testing                | current
   4 |       dave |               dave@example.org | Dave von Testing               | current
   5 |       erin |               erin@example.org | Erin von Testing               | current
   6 |     howard |             howard@example.org | Howard von Testing             | current
   7 |      extra |              extra@example.org | Extra von Testing              | retired

"""

# Scenario: Default / human readable format.
try:
    output = instance.execute(["sudo", "criticctl", "listusers"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "-f", "table"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "--format", "table"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

expected = """\
# id, name, email, fullname, status
[
 (1, 'admin', 'admin@example.org', 'Testing Administrator', 'current'),
 (2, 'alice', 'alice@example.org', 'Alice von Testing', 'current'),
 (3, 'bob', 'bob@example.org', 'Bob von Testing', 'current'),
 (4, 'dave', 'dave@example.org', 'Dave von Testing', 'current'),
 (5, 'erin', 'erin@example.org', 'Erin von Testing', 'current'),
 (6, 'howard', 'howard@example.org', 'Howard von Testing', 'current'),
 (7, 'extra', 'extra@example.org', 'Extra von Testing', 'retired'),
]
"""

# Scenario: Tuples format.
try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "-f", "tuples"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "--format", "tuples"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

expected = """\
[
 {'id': 1, 'name': 'admin', 'email': 'admin@example.org', 'fullname': 'Testing Administrator', 'status': 'current'},
 {'id': 2, 'name': 'alice', 'email': 'alice@example.org', 'fullname': 'Alice von Testing', 'status': 'current'},
 {'id': 3, 'name': 'bob', 'email': 'bob@example.org', 'fullname': 'Bob von Testing', 'status': 'current'},
 {'id': 4, 'name': 'dave', 'email': 'dave@example.org', 'fullname': 'Dave von Testing', 'status': 'current'},
 {'id': 5, 'name': 'erin', 'email': 'erin@example.org', 'fullname': 'Erin von Testing', 'status': 'current'},
 {'id': 6, 'name': 'howard', 'email': 'howard@example.org', 'fullname': 'Howard von Testing', 'status': 'current'},
 {'id': 7, 'name': 'extra', 'email': 'extra@example.org', 'fullname': 'Extra von Testing', 'status': 'retired'},
]
"""

# Scenario: Dicts format.
try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "-f", "dicts"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.execute(["sudo", "criticctl", "listusers",
                               "--format", "dicts"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check(expected, output)
