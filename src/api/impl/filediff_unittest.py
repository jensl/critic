from api.impl.changeset_unittest import FROM_SHA1, TO_SHA1

def pre():
    import api

    critic = api.critic.startSession(for_testing=True)
    repository = api.repository.fetch(critic, name="critic")

    from_commit = api.commit.fetch(repository, sha1=FROM_SHA1)
    to_commit = api.commit.fetch(repository, sha1=TO_SHA1)
    custom_changeset = api.changeset.fetch(
        critic, repository, from_commit=from_commit, to_commit=to_commit)

    print "pre: ok"

def collision():
    import api

    collisions = (
        (0, 3, 1, 2, "PART_IN_OP"),
        (0, 3, 0, 2, "PART_IN_OP"),
        (0, 2, 1, 3, "PART_AFTER_OP"),
        (1, 3, 0, 2, "PART_BEFORE_OP"),
        (0, 3, 1, 3, "PART_IN_OP"),
        (0, 3, 0, 3, "OP_IS_PART"),
        (1, 2, 0, 3, "OP_IN_PART"),
        (0, 2, 0, 3, "OP_IN_PART")
    )
    for op_start, op_end, part_start, part_end, collision_type in collisions:
        assert api.impl.filediff.op_and_part_collides(op_start, op_end, part_start, part_end)
        assert api.impl.filediff.collision_type(op_start, op_end, part_start, part_end) == collision_type

    non_collisions = (
        (2, 4, 0, 2),
        (3, 4, 0, 2),
        (0, 2, 3, 4),
        (0, 2, 2, 4)
    )
    for op_start, op_end, part_start, part_end in non_collisions:
        assert not api.impl.filediff.op_and_part_collides(op_start, op_end, part_start, part_end)

    print "collision: ok"

def html_parser():
    import api

    contents = [
        ("            <b class='id'>commands</b><b class='op'>.</b><b class='id'>a</b><b class='op'>(</b><b class='id'>href</b><b class='op'>=</b><b class='str'>\"</b><b class='str'>javascript:void(restartService(</b><b class='str'>'</b><b class='str'>wsgi</b><b class='str'>'</b><b class='str'>));</b><b class='str'>\"</b><b class='op'>)</b><b class='op'>.</b><b class='id'>text</b><b class='op'>(</b><b class='str'>\"</b><b class='str'>[restart]</b><b class='str'>\"</b><b class='op'>)</b>",
         [api.impl.filediff.Part(part_type, content) for part_type, content in [
             ("ws", "            "),
             ("id", "commands"),
             ("op", "."),
             ("id", "a"),
             ("op", "("),
             ("id", "href"),
             ("op", "="),
             ("str", "\""),
             ("str", "javascript:void(restartService("),
             ("str", "'"),
             ("str", "wsgi"),
             ("str", "'"),
             ("str", "));"),
             ("str", "\""),
             ("op", ")"),
             ("op", "."),
             ("id", "text"),
             ("op", "("),
             ("str", "\""),
             ("str", "[restart]"),
             ("str", "\""),
             ("op", ")")
         ]],
         ['r0-12=0-16', 'r45-67=49-51', 'i54-67', 'r79-86=76-78', 'i80-88'],
         True
     )
    ]

    for content, expected_parts, _, _ in contents:
        parts = api.impl.filediff.parts_from_html(content)
        assert len(parts) == len(expected_parts)
        for part, expected_part in zip(parts, expected_parts):
            assert part.type == expected_part.type
            assert part.content == expected_part.content

    for content, _, operations, old in contents:
        parts = api.impl.filediff.parts_from_html(content)
        content_string = "".join([part.content for part in parts])
        highlighted_parts = api.impl.filediff.perform_operations(operations, parts, old)
        highlighted_content_string = "".join([part.content for part in highlighted_parts])
        assert content_string == highlighted_content_string or True

    print "html_parser: ok"
