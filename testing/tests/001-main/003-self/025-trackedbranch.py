import time
import re

BRANCH_NAME = "025-trackedbranch"

def normalize_whitespace(message):
    return re.sub(r"\s+", " ", message.strip())

def split_hook_output(output):
    title, _, message = output.partition("\n\n")
    return normalize_whitespace(title), normalize_whitespace(message)

def split_git_output(output):
    return split_hook_output(
        "\n".join(line[len("remote: "):]
                  for line in output.splitlines()
                  if line.startswith("remote: ")))

with repository.workcopy() as work, frontend.signin():
    REMOTE_URL = instance.repository_url("alice")

    def wait_for_branch(branch_name, value):
        instance.synchronize_service("branchtracker")

        try:
            output = work.run(["ls-remote", "--exit-code", REMOTE_URL,
                               "refs/heads/" + branch_name])
            if output.startswith(value):
                return
        except testing.repository.GitCommandError:
            logger.error("Tracked branch %s not updated as expected."
                         % branch_name)
            raise testing.TestFailure

    def get_branch_log(branch_id, expected_length):
        result = frontend.operation(
            "trackedbranchlog",
            data={ "branch_id": branch_id })

        branch_log = result["items"]

        testing.expect.check(expected_length, len(branch_log))

        return branch_log

    def check_log_item(branch_log_item, from_sha1, to_sha1, hook_output,
                       successful):
        testing.expect.check(from_sha1, branch_log_item["from_sha1"])
        testing.expect.check(to_sha1, branch_log_item["to_sha1"])
        if isinstance(hook_output, tuple):
            expected_title, expected_message = hook_output
            actual_title, actual_message = split_hook_output(
                branch_log_item["hook_output"])
            testing.expect.check(expected_title, actual_title)
            testing.expect.check(expected_message, actual_message)
        else:
            testing.expect.check(hook_output, branch_log_item["hook_output"])
        testing.expect.check(successful, branch_log_item["successful"])

    work.run(["push", "origin", "HEAD:refs/heads/" + BRANCH_NAME])

    sha1s = { "HEAD": work.run(["rev-parse", "HEAD"]).strip(),
              "HEAD^": work.run(["rev-parse", "HEAD^"]).strip() }

    result = frontend.operation(
        "addtrackedbranch",
        data={ "repository_id": 1,
               "source_location": repository.url,
               "source_name": BRANCH_NAME,
               "target_name": BRANCH_NAME,
               "users": ["alice"],
               "forced": False })

    branch_id = result["branch_id"]

    wait_for_branch(BRANCH_NAME, sha1s["HEAD"])

    branch_log = get_branch_log(branch_id, expected_length=1)

    check_log_item(branch_log[0],
                   from_sha1="0" * 40,
                   to_sha1=sha1s["HEAD"],
                   hook_output="",
                   successful=True)

    try:
        work.run(
            ["push", REMOTE_URL, "-f", "HEAD^:refs/heads/" + BRANCH_NAME],
            TERM="dumb")
    except testing.repository.GitCommandError as error:
        title, message = split_git_output(error.output)
        testing.expect.check(
            ("%s rejected: invalid branch update: tracking branch"
             % BRANCH_NAME),
            title)
        testing.expect.check(
            (("The branch %s in this repository tracks %s in %s, and should "
              "not be updated directly in this repository.")
             % (BRANCH_NAME, BRANCH_NAME, repository.url)),
            message)
    else:
        testing.expect.check(
            "<rejected update of tracking branch>",
            "<update was accepted>")

    try:
        work.run(
            ["push", REMOTE_URL, "-f", ":refs/heads/" + BRANCH_NAME],
            TERM="dumb")
    except testing.repository.GitCommandError as error:
        title, message = split_git_output(error.output)
        testing.expect.check(
            ("%s rejected: invalid branch deletion: tracking branch"
             % BRANCH_NAME),
            title)
        testing.expect.check(
            (("The branch %s in this repository tracks %s in %s, and should "
              "not be deleted in this repository.")
             % (BRANCH_NAME, BRANCH_NAME, repository.url)),
            message)
    else:
        testing.expect.check(
            "<rejected update of tracking branch>",
            "<update was accepted>")

    # FIXME: This used to test error handling of rejection of non-fast-forward
    #        updates via branch tracking. But this is no longer rejected, so
    #        checking this is not possible now.

    # work.run(["push", "origin", "-f", "HEAD^:refs/heads/" + BRANCH_NAME])

    # frontend.operation(
    #     "triggertrackedbranchupdate",
    #     data={ "branch_id": branch_id })

    # instance.synchronize_service("branchtracker")

    # log_entries = instance.filter_service_log("branchtracker", "error")

    # testing.expect.check(1, len(log_entries))
    # testing.expect.check("ERROR - update of branch 025-trackedbranch from "
    #                      "025-trackedbranch in %s failed" % repository.url,
    #                      log_entries[0].splitlines()[0])

    # to_system = testing.mailbox.ToRecipient("system@example.org")
    # system_subject = testing.mailbox.WithSubject(
    #     "branchtracker.log: update of branch %s from %s in %s failed"
    #     % (BRANCH_NAME, BRANCH_NAME, repository.url))
    # mailbox.pop(accept=[to_system, system_subject])

    # to_alice = testing.mailbox.ToRecipient("alice@example.org")
    # alice_subject = testing.mailbox.WithSubject(
    #     "%s: update from %s in %s" % (BRANCH_NAME, BRANCH_NAME, repository.url))
    # mailbox.pop(accept=[to_alice, alice_subject])

    # branch_log = get_branch_log(branch_id, expected_length=2)

    # check_log_item(branch_log[0],
    #                from_sha1="0" * 40,
    #                to_sha1=sha1s["HEAD"],
    #                hook_output="",
    #                successful=True)
    # check_log_item(branch_log[1],
    #                from_sha1=sha1s["HEAD"],
    #                to_sha1=sha1s["HEAD^"],
    #                hook_output=(
    #                    ("%s rejected: invalid branch update: "
    #                     "non-fast-forward update"
    #                     % BRANCH_NAME),
    #                    "This tracked branch is not in \"forced\" mode, thus "
    #                    "rejecting the update."),
    #                successful=False)

    work.run(["push", "origin", "HEAD:refs/heads/%s-forced" % BRANCH_NAME])

    result = frontend.operation(
        "addtrackedbranch",
        data={ "repository_id": 1,
               "source_location": repository.url,
               "source_name": BRANCH_NAME + "-forced",
               "target_name": BRANCH_NAME + "-forced",
               "users": ["alice"],
               "forced": True })

    branch_id = result["branch_id"]

    wait_for_branch(BRANCH_NAME + "-forced", sha1s["HEAD"])

    branch_log = get_branch_log(branch_id, expected_length=1)

    check_log_item(branch_log[0],
                   from_sha1="0" * 40,
                   to_sha1=sha1s["HEAD"],
                   hook_output="",
                   successful=True)

    work.run(["push", "origin", "-f", "HEAD^:refs/heads/%s-forced" % BRANCH_NAME])

    frontend.operation(
        "triggertrackedbranchupdate",
        data={ "branch_id": branch_id })

    wait_for_branch(BRANCH_NAME + "-forced", sha1s["HEAD^"])

    branch_log = get_branch_log(branch_id, expected_length=2)

    check_log_item(branch_log[0],
                   from_sha1="0" * 40,
                   to_sha1=sha1s["HEAD"],
                   hook_output="",
                   successful=True)
    check_log_item(branch_log[1],
                   from_sha1=sha1s["HEAD"],
                   to_sha1=sha1s["HEAD^"],
                   hook_output="",
                   successful=True)

    mailbox.check_empty()
