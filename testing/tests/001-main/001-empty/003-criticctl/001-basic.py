def expect_success(argv, expected_output_lines=[]):
    try:
        output = instance.execute(argv)
    except testing.virtualbox.GuestCommandError as error:
        logger.error("'%s': correct criticctl usage failed:\n%s"
                     % (" ".join(argv), error.stdout))
        return []
    else:
        output_lines = set(map(str.strip, output.splitlines()))
        for line in expected_output_lines:
            if line.strip() not in output_lines:
                logger.error("'%s': Expected output line not found:\n  %r"
                             % (" ".join(argv), line))
        return output_lines

def expect_failure(argv, expected_output_lines=[]):
    try:
        instance.execute(argv)
    except testing.virtualbox.GuestCommandError as error:
        output_lines = set(map(str.strip, error.stderr.splitlines()))
        for line in expected_output_lines:
            if line.strip() not in output_lines:
                logger.error("'%s': Expected output line not found:\n  %r"
                             % (" ".join(argv), line))
        return output_lines
    else:
        logger.error("'%s': incorrect criticctl usage did not fail"
                     % " ".join(argv))
        return []

expect_failure(["criticctl"],
               ["ERROR: Failed to set UID = critic. Run as root?"])

# Test -h/--help argument.
usage_lines = expect_success(["sudo", "criticctl"],
                             ["Critic administration interface",
                              "Available commands are:"])
expect_success(["sudo", "criticctl", "-h"],
               usage_lines)
expect_success(["sudo", "criticctl", "--help"],
               usage_lines)

# Test --etc-dir/-e argument.
expect_success(["sudo", "criticctl", "--etc-dir", "/etc/critic"],
               usage_lines)
expect_success(["sudo", "criticctl", "--etc-dir=/etc/critic"],
               usage_lines)
expect_success(["sudo", "criticctl", "-e", "/etc/critic"],
               usage_lines)
expect_success(["sudo", "criticctl", "-e/etc/critic"],
               usage_lines)
lines = expect_failure(["sudo", "criticctl", "--etc-dir", "/etc/wrong"],
                       ["ERROR: Directory is inaccessible: /etc/wrong"])
expect_failure(["sudo", "criticctl", "-e", "/etc/wrong"],
               lines)
lines = expect_failure(["sudo", "criticctl", "--etc-dir"],
                       ["criticctl: error: argument --etc-dir/-e: "
                        "expected one argument"])
expect_failure(["sudo", "criticctl", "-e"],
               lines)

# Test --identity/-i argument.
expect_success(["sudo", "criticctl", "--identity", "main"],
               usage_lines)
expect_success(["sudo", "criticctl", "--identity=main"],
               usage_lines)
expect_success(["sudo", "criticctl", "-i", "main"],
               usage_lines)
expect_success(["sudo", "criticctl", "-imain"],
               usage_lines)
lines = expect_failure(["sudo", "criticctl", "--identity", "wrong"],
                       ["ERROR: Invalid identity: wrong"])
expect_failure(["sudo", "criticctl", "-i", "wrong"],
               lines)
lines = expect_failure(["sudo", "criticctl", "--identity"],
                       ["criticctl: error: argument --identity/-i: "
                        "expected one argument"])
expect_failure(["sudo", "criticctl", "-i"],
               lines)

# Test unknown arguments.
expect_failure(["sudo", "criticctl", "-x"],
               ["criticctl: error: unrecognized arguments: -x"])
expect_failure(["sudo", "criticctl", "--xxx"],
               ["criticctl: error: unrecognized arguments: --xxx"])

# Test unknown command.
lines = expect_failure(["sudo", "criticctl", "foo"],
                       ["ERROR: Invalid command: foo"])
expect_failure(["sudo", "criticctl", "-e", "/etc/critic", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-e/etc/critic", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-i", "main", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-imain", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-e", "/etc/critic", "-i", "main", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-e/etc/critic", "-imain", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-i", "main", "-e", "/etc/critic", "foo"],
               lines)
expect_failure(["sudo", "criticctl", "-imain", "-e/etc/critic", "foo"],
               lines)
