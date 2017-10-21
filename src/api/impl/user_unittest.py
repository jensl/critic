def basic(arguments):
    import api

    critic = api.critic.startSession(for_testing=True)

    alice = api.user.fetch(critic, name="alice")
    bob = api.user.fetch(critic, name="bob")
    carol = api.user.fetch(critic, name="carol")
    dave = api.user.fetch(critic, name="dave")
    erin = api.user.fetch(critic, name="erin")
    felix = api.user.fetch(critic, name="felix")
    howard = api.user.fetch(critic, name="howard")
    gina = api.user.fetch(critic, name="gina")
    iris = api.user.fetch(critic, name="iris")
    admin = api.user.fetch(critic, name="admin")
    extra = api.user.fetch(critic, name="extra")

    all_users = [admin, alice, bob, dave, erin, howard,
                 carol, felix, gina, iris, extra]

    assert isinstance(alice, api.user.User)
    assert isinstance(alice.id, int)
    assert int(alice) == alice.id
    assert hash(alice) == hash(alice.id)
    assert alice == alice.id
    assert alice.id == alice

    assert alice.name == "alice"
    assert alice.fullname == "Alice von Testing"
    assert alice.status == "current"
    assert alice.email == "alice@example.org"
    assert alice.is_anonymous is False

    assert isinstance(alice.primary_emails, list)
    assert len(alice.primary_emails) == 1
    assert isinstance(alice.primary_emails[0], api.user.User.PrimaryEmail)
    assert alice.primary_emails[0].address == "alice@example.org"
    assert alice.primary_emails[0].selected is True
    assert alice.primary_emails[0].verified is None

    assert isinstance(alice.git_emails, set)
    if len(alice.git_emails) == 0:
        assert arguments.unreliable_git_emails
    else:
        assert len(alice.git_emails) == 2
        assert "alice@example.org" in alice.git_emails
        assert "common@example.org" in alice.git_emails

    assert isinstance(alice.repository_filters, dict)
    assert len(alice.repository_filters) == 1
    repository, filters = list(alice.repository_filters.items())[0]
    assert isinstance(repository, api.repository.Repository)
    assert repository.name == "critic"
    assert len(filters) == 1
    assert isinstance(filters[0], api.filters.RepositoryFilter)
    assert filters[0].subject is alice
    assert filters[0].type == "reviewer"
    assert filters[0].path == "028-gitemails/"
    assert isinstance(filters[0].id, int)
    assert filters[0].repository is repository
    assert isinstance(filters[0].delegates, frozenset)
    assert all(isinstance(delegate, api.user.User)
               for delegate in filters[0].delegates)
    assert erin in filters[0].delegates

    assert not (alice == bob)
    assert alice != bob

    try:
        api.user.fetch(alice, user_id=alice.id)
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.user.fetch(critic)
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.user.fetch(critic, user_id=alice.id, name=alice.name)
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.user.fetch(critic, user_id="foo")
    except ValueError:
        pass
    else:
        assert False

    try:
        api.user.fetch(critic, user_id=4711)
    except api.user.InvalidUserId as error:
        assert error.message == "Invalid user id: %r" % 4711
        assert error.value == 4711
    else:
        assert False

    try:
        api.user.fetch(critic, name="nobody")
    except api.user.InvalidUserName as error:
        assert error.message == "Invalid user name: %r" % "nobody"
        assert error.value == "nobody"
    else:
        assert False

    try:
        api.user.fetchMany(alice, user_ids=[alice.id])
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.user.fetchMany(critic,
                           user_ids=[alice.id],
                           names=[alice.name])
    except AssertionError:
        pass
    else:
        assert False

    try:
        api.user.fetchMany(critic, user_ids=[4711, 4712])
    except api.user.InvalidUserIds as error:
        assert error.message == "Invalid user ids: %r" % [4711, 4712], error.message
        assert error.values == [4711, 4712], repr(error.values)
    else:
        assert False

    try:
        api.user.fetchMany(critic, names=["nobody", "anybody"])
    except api.user.InvalidUserNames as error:
        assert error.message == "Invalid user names: %r" % ["nobody", "anybody"], error.message
        assert error.values == ["nobody", "anybody"], repr(error.values)
    else:
        assert False

    alice_bob_and_dave = api.user.fetchMany(
        critic, user_ids=[alice.id, bob.id, dave.id])

    assert isinstance(alice_bob_and_dave, list), type(alice_bob_and_dave)
    assert alice_bob_and_dave == [alice, bob, dave], repr(alice_bob_and_dave)

    alice_bob_and_dave = api.user.fetchMany(
        critic, names=[alice.name, bob.name, dave.name])

    assert isinstance(alice_bob_and_dave, list), type(alice_bob_and_dave)
    assert alice_bob_and_dave == [alice, bob, dave], repr(alice_bob_and_dave)

    alice_bob_and_dave = api.user.fetchMany(
        critic, user_ids=set([alice.id, bob.id, dave.id]))

    assert isinstance(alice_bob_and_dave, set), type(alice_bob_and_dave)
    assert alice_bob_and_dave == set([alice, bob, dave]), repr(alice_bob_and_dave)

    alice_bob_and_dave = api.user.fetchMany(
        critic, names=set([alice.name, bob.name, dave.name]))

    assert isinstance(alice_bob_and_dave, set), type(alice_bob_and_dave)
    assert alice_bob_and_dave == set([alice, bob, dave]), repr(alice_bob_and_dave)

    alice_bob_and_dave = api.user.fetchMany(
        critic, user_ids=(user.id for user in [alice, bob, dave]))

    assert isinstance(alice_bob_and_dave, list), type(alice_bob_and_dave)
    assert alice_bob_and_dave == [alice, bob, dave], repr(alice_bob_and_dave)

    alice_bob_and_dave = api.user.fetchMany(
        critic, names=(user.name for user in [alice, bob, dave]))

    assert isinstance(alice_bob_and_dave, list), type(alice_bob_and_dave)
    assert alice_bob_and_dave == [alice, bob, dave], repr(alice_bob_and_dave)

    users = api.user.fetchAll(critic)
    assert isinstance(users, list)
    assert users == sorted(all_users, key=lambda user: user.id)

    users = api.user.fetchAll(critic, status="current")
    assert isinstance(users, list)
    assert users == sorted([user for user in all_users
                            if user.status == "current"],
                           key=lambda user: user.id)

    users = api.user.fetchAll(critic, status=["current", "absent"])
    assert isinstance(users, list)
    assert users == sorted([user for user in all_users
                            if user.status in ("current", "absent")],
                           key=lambda user: user.id)

    users = api.user.fetchAll(critic, status=["retired", "absent"])
    assert isinstance(users, list)
    assert users == sorted([user for user in all_users
                            if user.status in ("retired", "absent")],
                           key=lambda user: user.id)

    users = api.user.fetchAll(critic, status=["absent"])
    assert isinstance(users, list)
    assert users == []

    users = api.user.fetchAll(
        critic, status=(status for status in ["current", "absent"]))
    assert isinstance(users, list)
    assert users == sorted([user for user in all_users
                            if user.status in ("current", "absent")],
                           key=lambda user: user.id)

    assert alice.hasRole("administrator") is False
    assert alice.hasRole("repositories") is False
    assert alice.hasRole("newswriter") is False
    assert alice.hasRole("developer") is False

    assert admin.hasRole("administrator") is True
    assert admin.hasRole("repositories") is True
    if arguments.unreliable_admin_newswriter:
        assert isinstance(admin.hasRole("newswriter"), bool)
    else:
        assert admin.hasRole("newswriter") is True
    assert admin.hasRole("developer") is True

    try:
        alice.hasRole("crazy-cat-lady")
    except api.user.InvalidRole as error:
        assert error.message == "Invalid role: %r" % "crazy-cat-lady", error.message
        assert error.role == "crazy-cat-lady", error.role
    else:
        assert False

    anonymous = api.user.anonymous(critic)

    assert isinstance(anonymous, api.user.User)
    assert anonymous.id is None
    assert anonymous.name is None
    assert anonymous.fullname is None
    assert anonymous.is_anonymous is True
    assert anonymous.email is None
    assert anonymous.primary_emails == []
    assert anonymous.git_emails == set([])
    assert anonymous.repository_filters == {}

    print("basic: ok")

def preferences():
    import api

    critic = api.critic.startSession(for_testing=True)
    alice = api.user.fetch(critic, name="alice")
    repository = api.repository.fetch(critic, name="critic")

    compactMode = alice.getPreference("commit.diff.compactMode")
    assert isinstance(compactMode.value, bool)
    assert compactMode.item == "commit.diff.compactMode"
    assert compactMode.value is True
    assert compactMode.user is None
    assert compactMode.repository is None

    rulerColumn = alice.getPreference("commit.diff.rulerColumn")
    assert isinstance(rulerColumn.value, int)
    assert rulerColumn.item == "commit.diff.rulerColumn"
    assert rulerColumn.value == 0
    assert rulerColumn.user is None
    assert rulerColumn.repository is None

    defaultGroups = alice.getPreference("dashboard.defaultGroups")
    assert isinstance(defaultGroups.value, str)
    assert defaultGroups.item == "dashboard.defaultGroups"
    assert defaultGroups.value == "owned,draft,active,watched"
    assert defaultGroups.user is None
    assert defaultGroups.repository is None

    # Read per-repository, not overridden.
    compactMode = alice.getPreference("commit.diff.compactMode",
                                      repository=repository)
    assert compactMode.item == "commit.diff.compactMode"
    assert compactMode.value is True
    assert compactMode.user is None
    assert compactMode.repository is None

    # Read per-user, overridden per user.
    visualTabs = alice.getPreference("commit.diff.visualTabs")
    assert visualTabs.value is True
    assert visualTabs.user is alice
    assert visualTabs.repository is None

    # Read per-repository, overridden per user.
    visualTabs = alice.getPreference("commit.diff.visualTabs",
                                     repository=repository)
    assert visualTabs.value is True
    assert visualTabs.user is alice
    assert visualTabs.repository is None

    # Read per-user, overridden per repository.
    expandAllFiles = alice.getPreference("commit.expandAllFiles")
    assert expandAllFiles.value is False
    assert expandAllFiles.user is None
    assert expandAllFiles.repository is None

    # Read per-repository, overridden per repository.
    expandAllFiles = alice.getPreference("commit.expandAllFiles",
                                         repository=repository)
    assert expandAllFiles.value is True
    assert expandAllFiles.user is alice
    assert expandAllFiles.repository is repository

    print("preferences: ok")

def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--unreliable-git-emails", action="store_true")
    parser.add_argument("--unreliable-admin-newswriter", action="store_true")
    parser.add_argument("tests", nargs=argparse.REMAINDER)

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "basic":
            basic(arguments)
        elif test == "preferences":
            preferences()
