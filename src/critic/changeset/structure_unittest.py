import stat


def diff_trees(arguments):
    from critic import api
    from critic import gitutils

    with api.critic.startSession(for_testing=True):
        pass

    repository = gitutils.Repository(path=arguments.repository_path)
    directory_name = arguments.directory_name
    commit_sha1 = arguments.commit_sha1

    # We expect the specified commit's parent to have added a directory named
    # |directory_name| containing the following:
    #
    #   file-to-nothing
    #   file-to-file
    #   file-to-symlink
    #   file-to-directory
    #   symlink-to-nothing
    #   symlink-to-file
    #   symlink-to-symlink
    #   symlink-to-directory
    #   directory-to-nothing/
    #   directory-to-file/
    #   directory-to-symlink/
    #   directory-to-directory/
    #
    # We expect the specified commit to instead have the following:
    #
    #   file-to-file
    #   file-to-symlink
    #   file-to-directory/
    #   symlink-to-file
    #   symlink-to-symlink
    #   symlink-to-directory/
    #   directory-to-file
    #   directory-to-symlink
    #   directory-to-directory/
    #   nothing-to-file
    #   nothing-to-symlink
    #   nothing-to-directory/
    #
    # All entries are named typeA-to-typeB, and change from typeA to typeB in
    # the specified commit relative its parent.  If the types are the same, the
    # content will have changed.
    #
    # All files are text files contain "old\n" or "new\n", symlinks point to the
    # paths "old" or "new", and directories contain a text file named "file"
    # containing "old\n" or "new\n".

    from .structure import diff_trees

    old_tree_sha1 = repository.revparse(commit_sha1 + "^1^{tree}")
    new_tree_sha1 = repository.revparse(commit_sha1 + "^{tree}")

    def is_nothing(path, entry, _):
        assert entry is None, (path, entry)

    def is_file(path, entry, sha1):
        assert stat.S_ISREG(entry.mode) and entry.sha1 == sha1, (path, entry, sha1)

    def is_symlink(path, entry, sha1):
        assert stat.S_ISLNK(entry.mode) and entry.sha1 == sha1, (path, entry, sha1)

    old_file_sha1 = "3367afdbbf91e638efe983616377c60477cc6612"
    new_file_sha1 = "3e757656cf36eca53338e520d134963a44f793f8"
    old_symlink_sha1 = "489ce0f857e7634a0eb9f328265a3e91fad49f61"
    new_symlink_sha1 = "3e5126c4e761fd09582fc517918a1601b218dff0"

    expected = {
        "file-to-nothing": (is_file, is_nothing),
        "file-to-file": (is_file, is_file),
        "file-to-symlink": (is_file, is_symlink),
        "file-to-directory": (is_file, is_nothing),
        "file-to-directory/file": (is_nothing, is_file),
        "symlink-to-nothing": (is_symlink, is_nothing),
        "symlink-to-file": (is_symlink, is_file),
        "symlink-to-symlink": (is_symlink, is_symlink),
        "symlink-to-directory": (is_symlink, is_nothing),
        "symlink-to-directory/file": (is_nothing, is_file),
        "directory-to-nothing/file": (is_file, is_nothing),
        "directory-to-file/file": (is_file, is_nothing),
        "directory-to-file": (is_nothing, is_file),
        "directory-to-symlink/file": (is_file, is_nothing),
        "directory-to-symlink": (is_nothing, is_symlink),
        "directory-to-directory/file": (is_file, is_file),
        "nothing-to-file": (is_nothing, is_file),
        "nothing-to-symlink": (is_nothing, is_symlink),
        "nothing-to-directory/file": (is_nothing, is_file),
    }

    for changed_entry in diff_trees(repository, old_tree_sha1, new_tree_sha1):
        base, _, path = changed_entry.path.partition("/")

        # Expect only changes under |directory_name|.
        assert base == directory_name, changed_entry.path

        check_old, check_new = expected.pop(path)

        if check_old is is_file:
            old_expected_sha1 = old_file_sha1
        elif check_old is is_symlink:
            old_expected_sha1 = old_symlink_sha1
        else:
            old_expected_sha1 = None

        if check_new is is_file:
            new_expected_sha1 = new_file_sha1
        elif check_new is is_symlink:
            new_expected_sha1 = new_symlink_sha1
        else:
            new_expected_sha1 = None

        check_old(path, changed_entry.old_entry, old_expected_sha1)
        check_new(path, changed_entry.new_entry, new_expected_sha1)

    assert not expected, expected

    print("diff_trees: ok")


def request(arguments):
    from .structure import request
    from critic import api
    from critic import gitutils

    with api.critic.startSession(for_testing=True) as critic:
        db = critic.database

        repository = gitutils.Repository.fromPath(db, arguments.repository_path)
        to_commit = gitutils.Commit.fromSHA1(db, repository, arguments.commit_sha1)
        from_commit = gitutils.Commit.fromSHA1(db, repository, to_commit.parents[0])

        changeset_id = request(
            db, repository.id, from_commit.getId(db), to_commit.getId(db)
        )

    print("request: ok")


def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--repository-path")
    parser.add_argument("--directory-name")
    parser.add_argument("--commit-sha1")
    parser.add_argument("tests", nargs="+")

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "diff_trees":
            diff_trees(arguments)
        elif test == "request":
            request(arguments)
