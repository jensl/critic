FROM_SHA1 = "573c5ff15ad95cfbc3e2f2efb0a638a4a78c17a7"
FROM_SINGLE_SHA1 = "aabc2b10c930a9e72fe9587a6e8634087bb3efe1"
TO_SHA1 = "6dc8e9c2d952028286d4b83475947bd0b1410860"

def pre():
    import api
    import datetime

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    custom_changeset("pre", api, critic, repository)
    direct_changeset("pre", api, critic, repository)

    print("pre: ok")


def post():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    custom_changeset("post", api, critic, repository)
    direct_changeset("post", api, critic, repository)

    print("post: ok")


def is_empty_changeset(changeset, changeset_type):
    return (changeset.id == None and
            changeset.type == changeset_type and
            changeset.files == None)

def check_types(changeset):
    return (isinstance(changeset.id, (int, long)) and
            isinstance(changeset.type, str) and
            isinstance(changeset.files, list))


def custom_changeset(phase, api, critic, repository):
    if phase == "pre":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        custom_changeset = api.changeset.fetch(critic,
                                               repository,
                                               from_commit=from_commit,
                                               to_commit=to_commit)
        assert is_empty_changeset(custom_changeset, "custom"),\
            "custom_changeset should be empty, but isn't"

    elif phase == "post":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        custom_changeset = api.changeset.fetch(critic,
                                               repository,
                                               from_commit=from_commit,
                                               to_commit=to_commit)
        assert (check_types(custom_changeset) and
                custom_changeset.type == "custom"),\
            "custom_changeset has incorrect types"

    else:
        raise Exception


def direct_changeset(phase, api, critic, repository):
    if phase == "pre":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        from_single_commit = api.commit.fetch(repository, sha1=FROM_SINGLE_SHA1)
        changeset = api.changeset.fetch(critic,
                                        repository,
                                        single_commit=single_commit)
        equiv_changeset = api.changeset.fetch(critic,
                                              repository,
                                              from_commit=from_single_commit,
                                              to_commit=single_commit)
        assert (changeset.type != None),\
            "Changeset type is None"
        assert (equiv_changeset.type != None),\
            "Equivalent changeset type is None"

    elif phase == "post":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        from_single_commit = api.commit.fetch(repository, sha1=FROM_SINGLE_SHA1)
        changeset = api.changeset.fetch(critic,
                                        repository,
                                        single_commit=single_commit)
        equiv_changeset = api.changeset.fetch(critic,
                                              repository,
                                              from_commit=from_single_commit,
                                              to_commit=single_commit)

        assert (changeset.id == equiv_changeset.id and
                changeset.type == equiv_changeset.type and
                sum([not file.id == otherfile.id for file,otherfile in
                     zip(changeset.files, equiv_changeset.files)]) == 0 and
                len(changeset.files) == len(equiv_changeset.files) and
                len(changeset.files) > 0),\
            "changeset and equiv_changeset isn't identical"

    else:
        raise Exception
