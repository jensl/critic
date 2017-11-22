# mypy: ignore-errors

from .changeset_unittest import FROM_SHA1, TO_SHA1


def pre1():
    from critic import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    try:
        api.changeset.fetch(
            critic, repository, from_commit=from_commit, to_commit=to_commit
        )
    except api.changeset.Delayed:
        pass

    print("pre1: ok")


def pre2():
    from critic import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    changeset = api.changeset.fetch(
        critic, repository, from_commit=from_commit, to_commit=to_commit
    )
    file = api.file.fetch(critic, path="src/operation/createreview.py")
    filechange = api.filechange.fetch(changeset, file)

    try:
        api.filediff.fetch(filechange).getMacroChunks(context_lines=3)
    except api.filediff.Delayed:
        pass
    else:
        assert False, "filediff not delayed as expected"

    print("pre2: ok")


def post():
    from critic import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)

    changeset = api.changeset.fetch(
        critic, repository, from_commit=from_commit, to_commit=to_commit
    )
    file = api.file.fetch(critic, path="src/operation/createreview.py")
    filechange = api.filechange.fetch(changeset, file)
    filediff = api.filediff.fetch(filechange)

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

    print("post: ok")


def macro_chunks():
    from ...api.impl.filediff import ChangedLines, MacroChunk, MacroChunks

    def test(changes, mcs_expected, *, context_lines=3, extra=[]):
        mcs_actual = MacroChunks(context_lines)
        mcs_actual.add_changes(changes)

        for side, begin, end in extra:
            mcs_actual.add_extra(side, begin, end)

        for index, (mc_actual, mc_expected) in enumerate(zip(mcs_actual, mcs_expected)):
            assert mc_actual == mc_expected, "%r != %r at index %d" % (
                mc_actual,
                mc_expected,
                index,
            )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=5,
                insert_offset=3,
                insert_count=4,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=10,
                delete_count=2,
                insert_offset=9,
                insert_count=7,
                analysis=None,
            ),
        ],
        [MacroChunk(old_offset=0, old_count=15, new_offset=0, new_count=19)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=5,
                insert_offset=3,
                insert_count=4,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=16,
                delete_count=2,
                insert_offset=15,
                insert_count=7,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=11, new_offset=0, new_count=10),
            MacroChunk(old_offset=13, old_count=8, new_offset=12, new_count=13),
        ],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=5,
                insert_offset=3,
                insert_count=4,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=16,
                delete_count=2,
                insert_offset=15,
                insert_count=7,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=11, new_offset=0, new_count=10),
            MacroChunk(old_offset=13, old_count=8, new_offset=12, new_count=13),
        ],
        extra=[("new", 11, 12)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=5,
                insert_offset=3,
                insert_count=4,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=16,
                delete_count=2,
                insert_offset=15,
                insert_count=7,
                analysis=None,
            ),
        ],
        [MacroChunk(old_offset=0, old_count=21, new_offset=0, new_count=25)],
        extra=[("new", 11, 13)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=3,
                insert_offset=3,
                insert_count=6,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=40,
                delete_count=6,
                insert_offset=43,
                insert_count=3,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=9, new_offset=0, new_count=12),
            MacroChunk(old_offset=33, old_count=16, new_offset=36, new_count=13),
        ],
        extra=[("old", 36, 38)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=3,
                insert_offset=3,
                insert_count=6,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=40,
                delete_count=6,
                insert_offset=43,
                insert_count=3,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=9, new_offset=0, new_count=12),
            MacroChunk(old_offset=37, old_count=12, new_offset=40, new_count=9),
        ],
        extra=[("old", 30, 34)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=3,
                insert_offset=3,
                insert_count=6,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=40,
                delete_count=6,
                insert_offset=43,
                insert_count=3,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=9, new_offset=0, new_count=12),
            MacroChunk(old_offset=37, old_count=12, new_offset=40, new_count=9),
        ],
        extra=[("new", 44, 46)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=3,
                insert_offset=3,
                insert_count=6,
                analysis=None,
            ),
            ChangedLines(
                delete_offset=40,
                delete_count=6,
                insert_offset=43,
                insert_count=3,
                analysis=None,
            ),
        ],
        [
            MacroChunk(old_offset=0, old_count=9, new_offset=0, new_count=12),
            MacroChunk(old_offset=37, old_count=14, new_offset=40, new_count=11),
        ],
        extra=[("new", 44, 48)],
    )

    test(
        [
            ChangedLines(
                delete_offset=3,
                delete_count=3,
                insert_offset=3,
                insert_count=6,
                analysis="3=3;4=5;5=8",
            ),
            ChangedLines(
                delete_offset=40,
                delete_count=6,
                insert_offset=43,
                insert_count=3,
                analysis="40=43;42=44;45=45",
            ),
        ],
        [
            MacroChunk(
                old_offset=0,
                old_count=9,
                new_offset=0,
                new_count=12,
                mapped_lines=[(3, 3, ""), (4, 5, ""), (5, 8, "")],
            ),
            MacroChunk(
                old_offset=37,
                old_count=12,
                new_offset=40,
                new_count=9,
                mapped_lines=[(40, 43, ""), (42, 44, ""), (45, 45, "")],
            ),
        ],
    )

    print("macro_chunks: ok")
