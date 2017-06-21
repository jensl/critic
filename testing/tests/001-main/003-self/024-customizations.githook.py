# Need a VM (full installation) to do customizations.
# @flag full

import re
import json

# Install the githook customization.
instance.execute(
    ["sudo", "mkdir", "-p", "/etc/critic/main/customization",
     "&&",
     "sudo", "touch", "/etc/critic/main/customization/__init__.py",
     "&&",
     "sudo", "cp", "critic/testing/input/customization/githook.py",
     "/etc/critic/main/customization",
     "&&",
     "sudo", "chown", "-R", "critic.critic", "/etc/critic/main/customization"])
instance.criticctl(["restart"])

with repository.workcopy() as work:
    REMOTE_URL = instance.repository_url("alice")

    def lsremote(ref_name):
        try:
            output = work.run(["ls-remote", "--exit-code", REMOTE_URL, ref_name])
        except testing.repository.GitCommandError:
            return None

        lines = output.splitlines()

        testing.expect.check(1, len(lines))
        testing.expect.check("[0-9a-f]{40}\t" + ref_name, lines[0],
                             equal=re.match)

        return lines[0][:40]

    def push(new_value, ref_name, expected_result):
        old_value = lsremote(ref_name)

        if new_value is not None:
            new_value = work.run(["rev-parse", new_value]).strip()

        try:
            output = work.run(["push", "--quiet", REMOTE_URL,
                               "%s:%s" % (new_value or "", ref_name)])
            testing.expect.check(expected_result, "ACCEPT")
        except testing.repository.GitCommandError as error:
            output = error.output
            testing.expect.check(expected_result, "REJECT")

        from_hook = "<no output>"
        for line in output.splitlines():
            line = line.partition("\x1b")[0]
            if line.startswith("remote: "):
                line = line[len("remote: "):].strip()
                if line:
                    from_hook = line
                    break

        testing.expect.check("^%s:" % expected_result, from_hook,
                             equal=re.match)
        try:
            data = json.loads(from_hook[7:])
        except ValueError:
            logger.exception("Invalid JSON: %r" % from_hook[7:])
        testing.expect.check({ "repository_path": "/var/git/critic.git",
                               "ref_name": ref_name,
                               "old_value": old_value,
                               "new_value": new_value },
                             data)
        if expected_result == "ACCEPT":
            testing.expect.check(new_value, lsremote(ref_name))
        else:
            testing.expect.check(old_value, lsremote(ref_name))

    push("HEAD", "refs/heads/reject-create", "REJECT")
    push("HEAD^", "refs/heads/reject-delete", "ACCEPT")
    push("HEAD", "refs/heads/reject-delete", "ACCEPT")
    push(None, "refs/heads/reject-delete", "REJECT")
    push("HEAD^", "refs/heads/reject-update", "ACCEPT")
    push("HEAD", "refs/heads/reject-update", "REJECT")
    push("HEAD^", "refs/heads/reject-nothing", "ACCEPT")
    push("HEAD", "refs/heads/reject-nothing", "ACCEPT")
    push(None, "refs/heads/reject-nothing", "ACCEPT")

# Remove the githook customization again.
instance.execute(
    ["sudo", "rm", "-f",
     "/etc/critic/main/customization/githook.py",
     "/etc/critic/main/customization/githook.pyc"])
instance.criticctl(["restart"])
