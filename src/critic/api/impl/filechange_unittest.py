# mypy: ignore-errors

from .changeset_unittest import (
    ROOT_PATHLIST,
    ROOT_SHA1,
    FROM_SHA1,
    TO_SHA1,
    CUSTOM_PATHLIST,
)


def pre():
    from critic import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    root_filechange("pre", api, critic, repository)
    custom_filechange("pre", api, critic, repository)
    single_filechange("pre", api, critic, repository)

    print("pre: ok")


def post():
    from critic import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    root_filechange("post", api, critic, repository)
    custom_filechange("post", api, critic, repository)
    single_filechange("post", api, critic, repository)

    print("post: ok")


# requires list of filechange objects
def assert_valid_filechanges(filechanges):
    for filechange in filechanges:
        assert filechange.old_sha1 != filechange.new_sha1
        if filechange.old_sha1 is not None:
            assert isinstance(filechange.old_sha1, str)
            assert len(filechange.old_sha1) == 40
        if filechange.new_sha1 is not None:
            assert filechange.new_sha1 is None or isinstance(filechange.new_sha1, str)
            assert len(filechange.new_sha1) == 40


def root_filechange(phase, api, critic, repository):
    if phase == "pre":
        root_commit = api.commit.fetch(repository, sha1=ROOT_SHA1)
        try:
            api.changeset.fetch(critic, repository, single_commit=root_commit)
        except api.changeset.Delayed:
            pass

    elif phase == "post":
        root_commit = api.commit.fetch(repository, sha1=ROOT_SHA1)
        root_changeset = api.changeset.fetch(
            critic, repository, single_commit=root_commit
        )
        root_filechanges = api.filechange.fetchAll(root_changeset)

        root_files = frozenset(
            [filechange.file.path for filechange in root_filechanges]
        )
        assert (
            root_files == ROOT_PATHLIST
        ), "files in filechanges differ from the expected"
        assert_valid_filechanges(root_filechanges)

    else:
        raise Exception


def custom_filechange(phase, api, critic, repository):
    if phase == "pre":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        try:
            api.changeset.fetch(
                critic, repository, from_commit=from_commit, to_commit=to_commit
            )
        except api.changeset.Delayed:
            pass

    elif phase == "post":
        from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
        to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        custom_changeset = api.changeset.fetch(
            critic, repository, from_commit=from_commit, to_commit=to_commit
        )
        for filechange in custom_changeset.files:
            assert_valid_filechanges([filechange])

    else:
        raise Exception


def single_filechange(phase, api, critic, repository):
    if phase == "pre":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        try:
            api.changeset.fetch(critic, repository, single_commit=single_commit)
        except api.changeset.Delayed:
            pass

    elif phase == "post":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        single_changeset = api.changeset.fetch(
            critic, repository, single_commit=single_commit
        )
        all_filechanges = api.filechange.fetchAll(single_changeset)
        assert_valid_filechanges(all_filechanges)
        all_filechange_ids = [filechange.file.id for filechange in all_filechanges]

        equiv_filechange_ids = [
            filechange.file.id for filechange in single_changeset.files
        ]

        assert frozenset(all_filechange_ids) == frozenset(equiv_filechange_ids)
    else:
        raise Exception
