from api.impl.changeset_unittest import FROM_SHA1, TO_SHA1

def pre1():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    try:
        api.changeset.fetch(
            critic, repository, from_commit=from_commit, to_commit=to_commit)
    except api.changeset.ChangesetDelayed:
        pass

    print "pre1: ok"

def pre2():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    changeset = api.changeset.fetch(
        critic, repository, from_commit=from_commit, to_commit=to_commit)
    file = api.file.fetch(critic, path="src/operation/createreview.py")
    filechange = api.filechange.fetch(critic, changeset, file)

    try:
        api.filediff.fetch(critic, filechange).getMacroChunks(context_lines=3)
    except api.filediff.FilediffDelayed:
        pass
    else:
        assert False, "filediff not delayed as expected"

    print "pre2: ok"

def post():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    changeset = api.changeset.fetch(
        critic, repository, from_commit=from_commit, to_commit=to_commit)
    file = api.file.fetch(critic, path="src/operation/createreview.py")
    filechange = api.filechange.fetch(critic, changeset, file)
    filediff = api.filediff.fetch(critic, filechange)

    chunks = filediff.getMacroChunks(context_lines=3)

    assert isinstance(chunks, list)
    assert len(chunks) == 2

    assert chunks[0].old_offset == 88
    assert chunks[0].old_count == 6
    assert chunks[0].new_offset == 88
    assert chunks[0].new_count == 9

    assert len(chunks[0].lines) == 9
    assert chunks[0].lines[0].type_string == "CONTEXT"
    assert chunks[0].lines[1].type_string == "CONTEXT"
    assert chunks[0].lines[2].type_string == "CONTEXT"
    assert chunks[0].lines[3].type_string == "INSERTED"
    assert chunks[0].lines[4].type_string == "INSERTED"
    assert chunks[0].lines[5].type_string == "INSERTED"
    assert chunks[0].lines[6].type_string == "CONTEXT"
    assert chunks[0].lines[7].type_string == "CONTEXT"
    assert chunks[0].lines[8].type_string == "CONTEXT"

    assert chunks[1].old_offset == 199
    assert chunks[1].old_count == 14
    assert chunks[1].new_offset == 202
    assert chunks[1].new_count == 15

    assert len(chunks[1].lines) == 15
    assert chunks[1].lines[0].type_string == "CONTEXT"
    assert chunks[1].lines[1].type_string == "CONTEXT"
    assert chunks[1].lines[2].type_string == "CONTEXT"
    assert chunks[1].lines[3].type_string == "MODIFIED"
    assert chunks[1].lines[4].type_string == "CONTEXT"
    assert chunks[1].lines[5].type_string == "CONTEXT"
    assert chunks[1].lines[6].type_string == "CONTEXT"
    assert chunks[1].lines[7].type_string == "CONTEXT"
    assert chunks[1].lines[8].type_string == "CONTEXT"
    assert chunks[1].lines[9].type_string == "MODIFIED"
    assert chunks[1].lines[10].type_string == "REPLACED"
    assert chunks[1].lines[11].type_string == "INSERTED"
    assert chunks[1].lines[12].type_string == "CONTEXT"
    assert chunks[1].lines[13].type_string == "CONTEXT"
    assert chunks[1].lines[14].type_string == "CONTEXT"

    print "post: ok"
