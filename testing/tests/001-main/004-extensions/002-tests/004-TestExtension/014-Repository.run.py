import re

RE_NAME_EMAIL = re.compile(r"(author|committer)\s+(.*?)\s+<(.*?)>")

with frontend.signin("alice"):
    result = frontend.operation(
        "evaluate",
        data={ "source": """\
var repository = new critic.Repository("critic");
var tree_sha1 = repository.revparse("HEAD^{tree}");
var parent_sha1 = repository.revparse("HEAD^");
var workcopy = repository.getWorkCopy();
var sha1 = workcopy.run("commit-tree", tree_sha1, "-p", parent_sha1,
                        { stdin: "Fix some stuff!\\n\\nFTW!\\n",
                          GIT_AUTHOR_NAME: "Bob von Testing",
                          GIT_AUTHOR_EMAIL: "bob@example.com",
                          GIT_COMMITTER_NAME: "Alice von Testing",
                          GIT_COMMITTER_EMAIL: "alice@example.com" });
sha1 = sha1.trim(); // includes a line-break
workcopy.run("push", "origin", sha1 + ":refs/heads/014-Repository.run-1");
return sha1;""" })

    with repository.workcopy() as work:
        REMOTE_URL = "alice@" + instance.hostname + ":/var/git/critic.git"

        work.run(["fetch", REMOTE_URL, "refs/heads/014-Repository.run-1"])

        message = None

        for line in work.run(["cat-file", "commit", "FETCH_HEAD"]).splitlines():
            if message is None:
                if not line:
                    message = []
                    continue

                match = RE_NAME_EMAIL.match(line)
                if match:
                    field, name, email = match.groups()

                    if field == "author":
                        testing.expect.check("Bob von Testing", name)
                        testing.expect.check("bob@example.com", email)
                    else:
                        testing.expect.check("Alice von Testing", name)
                        testing.expect.check("alice@example.com", email)
                elif not (line.startswith("tree") or line.startswith("parent")):
                    testing.logger.error("Unexpected line: %r" % line)
            else:
                message.append(line)

        testing.expect.check(["Fix some stuff!", "", "FTW!"], message)
