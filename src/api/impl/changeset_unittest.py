FROM_SHA1 = "573c5ff15ad95cfbc3e2f2efb0a638a4a78c17a7"
FROM_SINGLE_SHA1 = "aabc2b10c930a9e72fe9587a6e8634087bb3efe1"
TO_SHA1 = "6dc8e9c2d952028286d4b83475947bd0b1410860"
ROOT_SHA1 = "ee37c47f6f6a14afa6912c1cc58a9f49d2a29acd"

CUSTOM_PATHLIST = frozenset(["src/auth/accesscontrol.py",
                             "src/operation/__init__.py",
                             "src/operation/createreview.py",
                             "src/page/createreview.py",
                             "src/page/utils.py",
                             "testing/__init__.py",
                             "testing/repository.py",
                             "testing/virtualbox.py"])

SINGLE_PATHLIST = frozenset(["testing/__init__.py",
                             "testing/repository.py",
                             "testing/virtualbox.py"])

ROOT_PATHLIST = frozenset([".gitignore",
                           "CONTRIBUTORS",
                           "COPYING",
                           "INSTALL",
                           "MIT-LICENSE.txt",
                           "README",
                           "auth.py",
                           "background/__init__.py",
                           "background/branchtracker.py",
                           "background/branchtrackerhook.py",
                           "background/changeset.py",
                           "background/daemon.py",
                           "background/githook.py",
                           "background/highlight.py",
                           "background/maildelivery.py",
                           "background/servicemanager.py",
                           "background/utils.py",
                           "background/watchdog.py",
                           "base.py",
                           "batchprocessor.py",
                           "changeset/__init__.py",
                           "changeset/client.py",
                           "changeset/create.py",
                           "changeset/detectmoves.py",
                           "changeset/html.py",
                           "changeset/load.py",
                           "changeset/process.py",
                           "changeset/text.py",
                           "changeset/utils.py",
                           "clexer.py",
                           "cli.py",
                           "comments.pgsql",
                           "changeset/html.py",
                           "changeset/load.py",
                           "changeset/process.py",
                           "changeset/text.py",
                           "changeset/utils.py",
                           "clexer.py",
                           "cli.py",
                           "comments.pgsql",
                           "config.py.empty",
                           "critic.py",
                           "dbaccess.py",
                           "dbclean.sql",
                           "dbschema.comments.sql",
                           "dbschema.extensions.sql",
                           "dbschema.sql",
                           "dbutils.py",
                           "diff.py",
                           "diff/__init__.py",
                           "diff/analyze.py",
                           "diff/context.py",
                           "diff/html.py",
                           "diff/merge.py",
                           "diff/parse.py",
                           "diffutils.py",
                           "documentation/concepts.txt",
                           "down.py",
                           "extensions.py",
                           "gitutils.py",
                           "hooks/pre-receive",
                           "htmlutils.py",
                           "index.py",
                           "install.py",
                           "installation/__init__.py",
                           "installation/admin.py",
                           "installation/apache.py",
                           "installation/config.py",
                           "installation/criticctl.py",
                           "installation/database.py",
                           "installation/files.py",
                           "installation/git.py",
                           "installation/initd.py",
                           "installation/input.py",
                           "installation/paths.py",
                           "installation/prefs.py",
                           "installation/prereqs.py",
                           "installation/process.py",
                           "installation/system.py",
                           "installation/templates/configuration/__init__.py",
                           "installation/templates/configuration/base.py",
                           "installation/templates/configuration/database.py",
                           "installation/templates/configuration/executables.py",
                           "installation/templates/configuration/extensions.py",
                           "installation/templates/configuration/limits.py",
                           "installation/templates/configuration/mimetypes.py",
                           "installation/templates/configuration/paths.py",
                           "installation/templates/configuration/services.py",
                           "installation/templates/configuration/smtp.py",
                           "installation/templates/criticctl",
                           "installation/templates/initd",
                           "installation/templates/site",
                           "linkify.py",
                           "log/__init__.py",
                           "log/commitset.py",
                           "log/html.py",
                           "log/tree.py",
                           "mailutils.py",
                           "maintenance/check-branches.py",
                           "maintenance/check-commits.py",
                           "maintenance/dumppreferences.py",
                           "maintenance/installpreferences.py",
                           "maintenance/progress.py",
                           "operation/__init__.py",
                           "operation/addrepository.py",
                           "operation/autocompletedata.py",
                           "operation/blame.py",
                           "operation/createcomment.py",
                           "operation/createreview.py",
                           "operation/draftchanges.py",
                           "operation/editresource.py",
                           "operation/extensioninstallation.py",
                           "operation/fetchlines.py",
                           "operation/manipulateassignments.py",
                           "operation/manipulatecomment.py",
                           "operation/manipulatefilters.py",
                           "operation/manipulatereview.py",
                           "operation/manipulateuser.py",
                           "operation/markfiles.py",
                           "operation/news.py",
                           "operation/rebasereview.py",
                           "operation/recipientfilter.py",
                           "operation/servicemanager.py",
                           "operation/trackedbranch.py",
                           "page/__init__.py",
                           "page/addrepository.py",
                           "page/basic.py",
                           "page/branches.py",
                           "page/checkbranch.py",
                           "page/config.py",
                           "page/confirmmerge.py",
                           "page/createreview.py",
                           "page/dashboard.py",
                           "page/editresource.py",
                           "page/filterchanges.py",
                           "page/home.py",
                           "page/manageextensions.py",
                           "page/managereviewers.py",
                           "page/news.py",
                           "page/repositories.py",
                           "page/search.py",
                           "page/services.py",
                           "page/showbatch.py",
                           "page/showbranch.py",
                           "page/showcomment.py",
                           "page/showcommit.py",
                           "page/showfile.py",
                           "page/showreview.py",
                           "page/showreviewlog.py",
                           "page/showtree.py",
                           "page/statistics.py",
                           "page/tutorial.py",
                           "page/utils.py",
                           "path.pgsql",
                           "profiling.py",
                           "request.py",
                           "resources/.gitattributes",
                           "resources/.gitignore",
                           "resources/autocomplete.js",
                           "resources/basic.css",
                           "resources/basic.js",
                           "resources/branches.css",
                           "resources/branches.js",
                           "resources/changeset.css",
                           "resources/changeset.js",
                           "resources/checkbranch.css",
                           "resources/checkbranch.js",
                           "resources/comment.css",
                           "resources/comment.js",
                           "resources/config.css",
                           "resources/config.js",
                           "resources/confirmmerge.css",
                           "resources/confirmmerge.js",
                           "resources/createreview.css",
                           "resources/createreview.js",
                           "resources/dashboard.css",
                           "resources/dashboard.js",
                           "resources/diff.css",
                           "resources/editresource.css",
                           "resources/editresource.js",
                           "resources/favicon-dev.png",
                           "resources/favicon.png",
                           "resources/filterchanges.css",
                           "resources/filterchanges.js",
                           "resources/home.css",
                           "resources/home.js",
                           "resources/images/ui-bg_flat_75_aaaaaa_40x100.png",
                           "resources/images/ui-bg_glass_100_f5f0e5_1x400.png",
                           "resources/images/ui-bg_glass_25_cb842e_1x400.png",
                           "resources/images/ui-bg_glass_70_ede4d4_1x400.png",
                           "resources/images/ui-bg_highlight-hard_100_f4f0ec_1x100.png",
                           "resources/images/ui-bg_highlight-hard_65_fee4bd_1x100.png",
                           "resources/images/ui-bg_highlight-hard_75_f5f5b5_1x100.png",
                           "resources/images/ui-bg_inset-soft_100_f4f0ec_1x100.png",
                           "resources/images/ui-icons_c47a23_256x240.png",
                           "resources/images/ui-icons_cb672b_256x240.png",
                           "resources/images/ui-icons_f08000_256x240.png",
                           "resources/images/ui-icons_f35f07_256x240.png",
                           "resources/images/ui-icons_ff7519_256x240.png",
                           "resources/images/ui-icons_ffffff_256x240.png",
                           "resources/jquery-1.7.1.min.js",
                           "resources/jquery-tooltip.css",
                           "resources/jquery-tooltip.js",
                           "resources/jquery-ui-1.8.17.custom.css",
                           "resources/jquery-ui-1.8.17.custom.min.js",
                           "resources/jquery-ui-autocomplete-html.js",
                           "resources/jquery-ui.css",
                           "resources/jquery-ui.js",
                           "resources/jquery.js",
                           "resources/log.css",
                           "resources/log.js",
                           "resources/manageextensions.css",
                           "resources/manageextensions.js",
                           "resources/managereviewers.css",
                           "resources/managereviewers.js",
                           "resources/message.css",
                           "resources/newrepository.css",
                           "resources/newrepository.js",
                           "resources/news.css",
                           "resources/news.js",
                           "resources/repositories.css",
                           "resources/repositories.js",
                           "resources/review.css",
                           "resources/review.js",
                           "resources/seal-of-approval-left.png",
                           "resources/search.css",
                           "resources/search.js",
                           "resources/services.css",
                           "resources/services.js",
                           "resources/showbatch.css",
                           "resources/showbranch.css",
                           "resources/showcomment.js",
                           "resources/showfile.css",
                           "resources/showfile.js",
                           "resources/showreview.css",
                           "resources/showreview.js",
                           "resources/showreviewlog.css",
                           "resources/showtree.css",
                           "resources/statistics.css",
                           "resources/syntax.css",
                           "resources/tabify.css",
                           "resources/tabify.js",
                           "resources/tutorial.css",
                           "resources/tutorial.js",
                           "resources/whitespace.css",
                           "review/__init__.py",
                           "review/comment/__init__.py",
                           "review/filters.py",
                           "review/html.py",
                           "review/mail.py",
                           "review/report.py",
                           "review/utils.py",
                           "roles.sql",
                           "syntaxhighlight/__init__.py",
                           "syntaxhighlight/clexer.py",
                           "syntaxhighlight/context.py",
                           "syntaxhighlight/cpp.py",
                           "syntaxhighlight/generate.py",
                           "syntaxhighlight/generic.py",
                           "syntaxhighlight/request.py",
                           "textformatting.py",
                           "textutils.py",
                           "tutorials/checkbranch.txt",
                           "tutorials/rebasing.txt",
                           "tutorials/reconfiguring.txt",
                           "tutorials/repository.txt",
                           "tutorials/requesting.txt",
                           "tutorials/reviewing.txt",
                           "utf8utils.py",
                           "wsgi.py",
                           "wsgistartup.py"])

def pre():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    custom_changeset("pre", api, critic, repository)
    direct_changeset("pre", api, critic, repository)
    root_changeset("pre", api, critic, repository)
    bad_changesets("pre", api, critic, repository)

    print("pre: ok")


def post():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    custom_changeset("post", api, critic, repository)
    direct_changeset("post", api, critic, repository)
    root_changeset("post", api, critic, repository)

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

        try:
            api.changeset.fetch(critic,
                                repository,
                                from_commit=from_commit,
                                to_commit=to_commit)
        except api.changeset.ChangesetDelayed:
            pass

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

        paths = frozenset([filechange.file.path for filechange in custom_changeset.files])

        assert paths == CUSTOM_PATHLIST,\
            "files in changeset deviate from expected files"

    else:
        raise Exception


def direct_changeset(phase, api, critic, repository):
    if phase == "pre":
        single_commit = api.commit.fetch(repository, sha1=TO_SHA1)
        from_single_commit = api.commit.fetch(repository, sha1=FROM_SINGLE_SHA1)
        try:
            api.changeset.fetch(critic,
                                repository,
                                single_commit=single_commit)
        except api.changeset.ChangesetDelayed:
            pass

        try:
            api.changeset.fetch(critic,
                                repository,
                                from_commit=from_single_commit,
                                to_commit=single_commit)
        except api.changeset.ChangesetDelayed:
            pass

        try:
            api.changeset.fetch(critic,
                                repository,
                                from_commit=single_commit,
                                to_commit=from_single_commit)
        except api.changeset.ChangesetDelayed:
            pass

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

        assert (changeset.id == equiv_changeset.id),\
            "changeset and equiv_changeset have different ids"

        assert (changeset.type == equiv_changeset.type),\
            "changeset and equiv_changeset have different types"

        files = [filechange.file for filechange in changeset.files]
        equiv_files = [filechange.file for filechange in equiv_changeset.files]

        changeset_files = frozenset(
            (file.id, file.path) for file in files)
        changeset_paths = frozenset(file.path for file in files)
        equiv_changeset_files = frozenset(
            (file.id, file.path) for file in equiv_files)

        assert (changeset_files == equiv_changeset_files),\
            "changeset and equiv_changeset have different files"

        assert (changeset_paths == SINGLE_PATHLIST),\
            "changeset has other files than expected"

    else:
        raise Exception


def root_changeset(phase, api, critic, repository):
    if phase == "pre":
        root_commit = api.commit.fetch(repository, ref=ROOT_SHA1)
        try:
            api.changeset.fetch(critic, repository, single_commit=root_commit)
        except api.changeset.ChangesetDelayed:
            pass

    elif phase == "post":
        root_commit = api.commit.fetch(repository, ref=ROOT_SHA1)
        root_changeset = api.changeset.fetch(critic, repository, single_commit=root_commit)
        assert (root_changeset.type == "direct"),\
            "root_changeset should be direct changeset"
        assert (isinstance(root_changeset.id, int)),\
            "root_changeset.id should be integer"
        root_paths = frozenset([filechange.file.path for filechange in root_changeset.files])

        assert (root_paths == ROOT_PATHLIST),\
            "root_changeset has other files than expected"

    else:
        raise Exception


def bad_changesets(phase, api, critic, repository):
    if phase == "pre":
        params_list = [(None, None, None, None, AssertionError),
                       (-5, None, None, None, api.changeset.InvalidChangesetId),
                       (None, None, None, "00g0", api.repository.InvalidRef),
                       (None, "00g0", TO_SHA1, None, api.repository.InvalidRef),
                       (None, FROM_SHA1, "00g0", None, api.repository.InvalidRef),
                       (1, FROM_SHA1, TO_SHA1, TO_SHA1, AssertionError),
                       (None, TO_SHA1, TO_SHA1, None, AssertionError)]
        for (changeset_id, from_commit_ref, to_commit_ref, single_commit_ref,
             expected_error) in params_list:
            try:
                if from_commit_ref is not None:
                    from_commit = api.commit.fetch(
                        repository, ref=from_commit_ref)
                else:
                    from_commit = None
                if to_commit_ref is not None:
                    to_commit = api.commit.fetch(repository, ref=to_commit_ref)
                else:
                    to_commit = None
                if single_commit_ref is not None:
                    single_commit = api.commit.fetch(
                        repository, ref=single_commit_ref)
                else:
                    single_commit = None
                changeset = api.changeset.fetch(
                    critic, repository, id=changeset_id,
                    from_commit=from_commit, to_commit=to_commit,
                    single_commit=single_commit)
            except expected_error:
                pass
            else:
                assert False,\
                    "Invalid/missing parameters should raise exception"
    else:
        raise Exception
