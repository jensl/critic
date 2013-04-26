DUMP_USER = """\
var user = %s;
return [user.name, user.email, user.fullname, user.isAnonymous];"""

def dump_user(user):
    return DUMP_USER % user

with frontend.signin("alice"):
    frontend.operation(
        "evaluate",
        data={ "source": dump_user("critic.User.current") },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })

    frontend.operation(
        "evaluate",
        data={ "source": dump_user("new critic.User(%d)"
                                   % instance.userid("alice")) },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })

    frontend.operation(
        "evaluate",
        data={ "source": dump_user("new critic.User({ id: %d })"
                                   % instance.userid("alice")) },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })

    frontend.operation(
        "evaluate",
        data={ "source": dump_user("new critic.User('alice')") },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })

    frontend.operation(
        "evaluate",
        data={ "source": dump_user("new critic.User({ name: 'alice' })") },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })

    frontend.operation(
        "evaluate",
        data={ "source": dump_user("new critic.User({ id: %d, name: 'alice' })"
                                   % instance.userid("alice")) },
        expect={ "result": ["alice", "alice@example.org", "Alice von Testing", False] })
