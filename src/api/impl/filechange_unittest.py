from api.impl.changeset_unittest import ROOT_PATHLIST, ROOT_SHA1, FROM_SHA1,\
TO_SHA1, CUSTOM_PATHLIST

def pre():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    root_filechange("pre", api, critic, repository)
    custom_filechange("pre", api, critic, repository)
    single_filechange("pre", api, critic, repository)

    print("pre: ok")


def post():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    root_filechange("post", api, critic, repository)
    custom_filechange("post", api, critic, repository)
    single_filechange("post", api, critic, repository)

    print("post: ok")


# requires list of filechange objects
def assert_valid_filechanges(filechanges):
    for filechange in filechanges:
        assert (filechange.old_sha1 != filechange.new_sha1),\
            "Expected filechange.new_sha1 to be different from filechange.old_sha1"
        assert (isinstance(filechange.old_sha1, str)),\
            "Expected filechange.old_sha1 to be a string"
        assert (len(filechange.old_sha1) == 40),\
            "Expected filechange.old_sha1 to be 40 characters long"
        assert (isinstance(filechange.new_sha1, str)),\
            "Expected filechange.new_sha1 to be a string"
        assert (len(filechange.new_sha1) == 40),\
            "Expected filechange.new_sha1 to be 40 characters long"
        for chunk in filechange.chunks:
            assert (chunk.deleteoffset >= 0 and chunk.deletecount >= 0 and
                    chunk.insertoffset >= 0 and chunk.insertcount >= 0),\
                "numbers can't be less than 0"


def root_filechange(phase, api, critic, repository):
    if phase == "pre":
        root_commit = api.commit.fetch(repository, sha1=ROOT_SHA1)
        try:
            api.changeset.fetch(
                critic, repository, single_commit=root_commit)
        except api.changeset.ChangesetDelayed:
            pass

    elif phase == "post":
        root_commit = api.commit.fetch(repository, sha1=ROOT_SHA1)
        root_changeset = api.changeset.fetch(
            critic, repository, single_commit=root_commit)
        root_filechanges = api.filechange.fetchAll(critic, root_changeset)

        root_files = frozenset(
            [filechange.path for filechange in root_filechanges])
        assert (root_files == ROOT_PATHLIST),\
            "files in filechanges differ from the expected"
        assert_valid_filechanges(root_filechanges)

    else:
        raise Exception


def custom_filechange(phase, api, critic, repository):
    if phase == "pre":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        try:
            api.changeset.fetch(
                critic, repository, from_commit=from_commit, to_commit=to_commit)
        except api.changeset.ChangesetDelayed:
            pass

    elif phase == "post":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        custom_changeset = api.changeset.fetch(
            critic, repository, from_commit=from_commit, to_commit=to_commit)
        for file in custom_changeset.files:
            filechange = api.filechange.fetch(critic, custom_changeset, file.id)
            assert_valid_filechanges([filechange])

    else:
        raise Exception


def single_filechange(phase, api, critic, repository):
    if phase == "pre":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        try:
            api.changeset.fetch(
                critic, repository, single_commit=single_commit)
        except api.changeset.ChangesetDelayed:
            pass

    elif phase == "post":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        single_changeset = api.changeset.fetch(
            critic, repository, single_commit=single_commit)
        all_filechanges = api.filechange.fetchAll(critic, single_changeset)
        assert_valid_filechanges(all_filechanges)
        all_filechange_ids = [filechange.id for filechange in all_filechanges]

        equiv_filechange_ids = []
        file_ids = [file.id for file in single_changeset.files]
        for file_id in file_ids:
            filechange = api.filechange.fetch(critic, single_changeset, file_id)
            equiv_filechange_ids.append(filechange.id)

        assert True or (frozenset(all_filechange_ids) == frozenset(equiv_filechange_ids)),\
            "filechanges from fetchAll should be equal to list of filechanges fetched by file_id"

    else:
        raise Exception
