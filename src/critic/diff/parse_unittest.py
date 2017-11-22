def splitlines():
    from .parse import splitlines

    assert splitlines(None) == None
    assert splitlines("") == ""  # This is arguably weird.
    assert splitlines("foo\nbar\nfie\n") == ["foo", "bar", "fie"]
    assert splitlines("foo\nbar\nfie") == ["foo", "bar", "fie"]
    assert splitlines("foo\r\nbar\r\nfie\r\n") == ["foo\r", "bar\r", "fie\r"]
    assert splitlines("foo\r\nbar\r\nfie") == ["foo\r", "bar\r", "fie"]

    print("splitlines: ok")


def examine_files(arguments):
    from critic import api
    from critic import gitutils
    from .parse import examine_files

    with api.critic.startSession(for_testing=True):
        pass

    repository = gitutils.Repository(path=arguments.repository_path)
    commit = arguments.commit_sha1

    as_list = []
    as_list_expected = []
    as_dict = {}
    as_dict_expected = {}

    def check(path, expected):
        actual = examine_files(repository, commit, path)
        if expected is None:
            assert actual is None, "%s: %r is not None" % (path, actual)
        else:
            assert actual == expected, "%s: %r != %r" % (path, actual, expected)
        as_list.append(path)
        as_list_expected.append(expected)
        as_dict[path] = False
        as_dict_expected[path] = expected

    check("no such file", None)

    for argument in arguments.text_file:
        text_file, _, nlines = argument.partition(":")
        nlines = int(nlines)
        check(text_file, nlines)

    for empty_file in arguments.empty_file:
        check(empty_file, 0)

    for binary_file in arguments.binary_file:
        check(binary_file, "binary")

    as_list_actual = examine_files(repository, commit, as_list)
    assert isinstance(as_list_actual, list)
    assert as_list_actual == as_list_expected

    as_dict_actual = examine_files(repository, commit, as_dict)
    assert as_dict_actual is as_dict
    assert as_dict_actual == as_dict_expected

    print("examine_files: ok")


def whitespace_difference():
    from .parse import whitespace_difference

    blocks = list(whitespace_difference(["A", "B"], 1, ["C", "D", "E"], 2, 0))
    assert blocks == [], repr(blocks)

    blocks = list(
        whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            1,
            ["C", "D", "foo", "bar", "fie", "E"],
            2,
            3,
        )
    )
    assert blocks == [], repr(blocks)

    blocks = list(
        whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            1,
            ["C", "D", "foo", " bar", "fie", "E"],
            2,
            3,
        )
    )
    assert blocks == [(2, 1, 1, 3, 1, 1)], repr(blocks)

    blocks = list(
        whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            1,
            ["C", "D", " foo", " bar", " fie", "E"],
            2,
            3,
        )
    )
    assert blocks == [(1, 3, 3, 2, 3, 3)], repr(blocks)

    blocks = list(
        whitespace_difference(["foo", "bar", "fie"], 0, ["foo", " bar", "fie"], 0, 3)
    )
    assert blocks == [(1, 1, 1, 1, 1, 1)], repr(blocks)

    print("whitespace_difference: ok")


def with_whitespace_difference():
    from .parse import with_whitespace_difference

    def gen(*blocks):
        for block in blocks:
            yield block

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            ["C", "D", "foo", "bar", "fie", "E"],
            gen((0, 1, 1, 0, 2, 2), (4, 1, 1, 5, 1, 1)),
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (4, 1, 1, 5, 1, 1)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            ["C", "D", "foo", " bar", "fie", "E"],
            gen((0, 1, 1, 0, 2, 2), (4, 1, 1, 5, 1, 1)),
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (2, 1, 1, 3, 1, 1), (4, 1, 1, 5, 1, 1)], repr(
        blocks
    )

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar", "fie", "B"],
            ["C", "D", " foo", " bar", " fie", "E"],
            gen((0, 1, 1, 0, 2, 2), (4, 1, 1, 5, 1, 1)),
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (1, 3, 3, 2, 3, 3), (4, 1, 1, 5, 1, 1)], repr(
        blocks
    )

    blocks = list(
        with_whitespace_difference(
            ["foo", "bar", "A"], ["foo", "bar", "C", "D"], gen((2, 1, 1, 2, 2, 2))
        )
    )
    assert blocks == [(2, 1, 1, 2, 2, 2)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["foo", "bar", "A"], [" foo", "bar", "C", "D"], gen((2, 1, 1, 2, 2, 2))
        )
    )
    assert blocks == [(0, 1, 1, 0, 1, 1), (2, 1, 1, 2, 2, 2)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["foo", "bar", "A"], ["foo", " bar", "C", "D"], gen((2, 1, 1, 2, 2, 2))
        )
    )
    assert blocks == [(1, 1, 1, 1, 1, 1), (2, 1, 1, 2, 2, 2)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["foo", "bar", "A"], [" foo", " bar", "C", "D"], gen((2, 1, 1, 2, 2, 2))
        )
    )
    assert blocks == [(0, 2, 2, 0, 2, 2), (2, 1, 1, 2, 2, 2)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar"], ["C", "D", " foo", "bar"], gen((0, 1, 1, 0, 2, 2))
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (1, 1, 1, 2, 1, 1)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar"], ["C", "D", "foo", " bar"], gen((0, 1, 1, 0, 2, 2))
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (2, 1, 1, 3, 1, 1)], repr(blocks)

    blocks = list(
        with_whitespace_difference(
            ["A", "foo", "bar"], ["C", "D", " foo", " bar"], gen((0, 1, 1, 0, 2, 2))
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (1, 2, 2, 2, 2, 2)], repr(blocks)

    print("with_whitespace_difference: ok")


def merged_block():
    from .parse import merged_block

    assert merged_block((1, 1, 1, 3, 1, 1), (2, 2, 2, 4, 2, 2)) == (1, 3, 3, 3, 3, 3)
    assert merged_block((1, 1, 2, 3, 1, 2), (3, 2, 3, 5, 2, 3)) == (1, 3, 5, 3, 3, 5)
    assert merged_block((1, 1, 1, 3, 1, 1), (4, 2, 2, 6, 2, 2), context_between=2) == (
        1,
        3,
        5,
        3,
        3,
        5,
    )

    print("merged_block: ok")


def with_merged_adjacent():
    from .parse import with_merged_adjacent

    def gen(*blocks):
        for block in blocks:
            yield block

    # No adjancent blocks.
    blocks = list(
        with_merged_adjacent(
            gen(
                (0, 1, 1, 0, 2, 2),
                (2, 1, 1, 3, 1, 1),
                (4, 2, 2, 5, 1, 1),
                (7, 1, 1, 7, 1, 1),
            )
        )
    )
    assert blocks == [
        (0, 1, 1, 0, 2, 2),
        (2, 1, 1, 3, 1, 1),
        (4, 2, 2, 5, 1, 1),
        (7, 1, 1, 7, 1, 1),
    ], repr(blocks)

    # First two adjancent.
    blocks = list(
        with_merged_adjacent(
            gen(
                (0, 2, 2, 0, 3, 3),
                (2, 1, 1, 3, 1, 1),
                (4, 2, 2, 5, 1, 1),
                (7, 1, 1, 7, 1, 1),
            )
        )
    )
    assert blocks == [(0, 3, 3, 0, 4, 4), (4, 2, 2, 5, 1, 1), (7, 1, 1, 7, 1, 1)], repr(
        blocks
    )

    # Middle two adjancent.
    blocks = list(
        with_merged_adjacent(
            gen(
                (0, 1, 1, 0, 2, 2),
                (2, 2, 2, 3, 2, 2),
                (4, 2, 2, 5, 1, 1),
                (7, 1, 1, 7, 1, 1),
            )
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (2, 4, 4, 3, 3, 3), (7, 1, 1, 7, 1, 1)], repr(
        blocks
    )

    # Last two adjancent.
    blocks = list(
        with_merged_adjacent(
            gen(
                (0, 1, 1, 0, 2, 2),
                (2, 1, 1, 3, 1, 1),
                (4, 3, 3, 5, 2, 2),
                (7, 1, 1, 7, 1, 1),
            )
        )
    )
    assert blocks == [(0, 1, 1, 0, 2, 2), (2, 1, 1, 3, 1, 1), (4, 4, 4, 5, 3, 3)], repr(
        blocks
    )

    # All adjancent blocks.
    blocks = list(
        with_merged_adjacent(
            gen(
                (0, 2, 2, 0, 3, 3),
                (2, 2, 2, 3, 2, 2),
                (4, 3, 3, 5, 2, 2),
                (7, 1, 1, 7, 1, 1),
            )
        )
    )
    assert blocks == [(0, 8, 8, 0, 8, 8)], repr(blocks)

    print("with_merged_adjacent: ok")


def with_false_splits_merged():
    from .parse import with_false_splits_merged

    def gen(*blocks):
        for block in blocks:
            yield block

    blocks = list(
        with_false_splits_merged(
            [
                "context",
                "old line 1",
                "old line 2",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "old line 3",
                "old line 4",
                "context",
            ],
            [
                "context",
                "new line 1",
                "new line 2",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "purely context",
                "new line 3",
                "new line 4",
                "context",
            ],
            gen((1, 2, 2, 1, 2, 2), (13, 2, 2, 13, 2, 2)),
        )
    )
    assert blocks == [(1, 2, 2, 1, 2, 2), (13, 2, 2, 13, 2, 2)], repr(blocks)

    blocks = list(
        with_false_splits_merged(
            [
                "context",
                "old line 1",
                "old line 2",
                "purely context",
                "old line 3",
                "old line 4",
                "context",
            ],
            [
                "context",
                "new line 1",
                "new line 2",
                "purely context",
                "new line 3",
                "new line 4",
                "context",
            ],
            gen((1, 2, 2, 1, 2, 2), (4, 2, 2, 4, 2, 2)),
        )
    )
    assert blocks == [(1, 2, 2, 1, 2, 2), (4, 2, 2, 4, 2, 2)], repr(blocks)

    blocks = list(
        with_false_splits_merged(
            [
                "context",
                "  if (some condition)",
                "  {",
                "    conditional line",
                "  }",
                "context",
            ],
            [
                "context",
                "  if (completely different condition)",
                "  {",
                "    if (slightly modified condition)",
                "    {",
                "      conditional line",
                "    }",
                "  }",
                "context",
            ],
            gen((1, 1, 1, 1, 1, 1), (3, 1, 1, 3, 4, 4)),
        )
    )
    assert blocks == [(1, 2, 3, 1, 5, 6)], repr(blocks)

    print("with_false_splits_merged: ok")


def main(argv):
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--repository-path")
    parser.add_argument("--commit-sha1")
    parser.add_argument("--text-file", action="append")
    parser.add_argument("--empty-file", action="append")
    parser.add_argument("--binary-file", action="append")
    parser.add_argument("tests", nargs="+")

    arguments = parser.parse_args(argv)

    for test in arguments.tests:
        if test == "splitlines":
            splitlines()
        elif test == "examine_files":
            examine_files(arguments)
        elif test == "whitespace_difference":
            whitespace_difference()
        elif test == "with_whitespace_difference":
            with_whitespace_difference()
        elif test == "merged_block":
            merged_block()
        elif test == "with_merged_adjacent":
            with_merged_adjacent()
        elif test == "with_false_splits_merged":
            with_false_splits_merged()
