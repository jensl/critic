# @dependency 002-infrastructure/001-criticctl/002-adduser-deluser.py
# @users admin, alice, bob, dave, erin, howard

# Scenario: Invalid format.
try:
    instance.criticctl(["listusers", "--format", "oranges"])
except testing.CriticctlError as error:
    if "invalid choice: 'oranges'" not in error.stderr:
        logger.error(
            "criticctl failed with unexpected error message:\n%s" % error.stderr
        )
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
   7 |        N/A |                                | N/A                            | disabled

"""

# Scenario: Default / human readable format.
try:
    output = instance.criticctl(["listusers"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.criticctl(["listusers", "-f", "table"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.criticctl(["listusers", "--format", "table"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
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
 (7, '__disabled_7__', None, '(disabled account)', 'disabled'),
]
"""

# Scenario: Tuples format.
try:
    output = instance.criticctl(["listusers", "-f", "tuples"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.criticctl(["listusers", "--format", "tuples"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
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
 {'id': 7, 'name': '__disabled_7__', 'email': None, 'fullname': '(disabled account)', 'status': 'disabled'},
]
"""

# Scenario: Dicts format.
try:
    output = instance.criticctl(["listusers", "-f", "dicts"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    testing.expect.check(expected, output)

try:
    output = instance.criticctl(["listusers", "--format", "dicts"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    testing.expect.check(expected, output)
