def expect_success(argv, expected_output_lines=[]):
    try:
        output = instance.criticctl(argv)
    except testing.CriticctlError as error:
        logger.error("'criticctl %s': correct criticctl usage failed:\n%s"
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
        instance.criticctl(argv)
    except testing.CriticctlError as error:
        output_lines = set(map(str.strip, error.stderr.splitlines()))
        for line in expected_output_lines:
            if line.strip() not in output_lines:
                logger.error("'%s': Expected output line not found:\n  %r"
                             % (" ".join(argv), line))
        return output_lines
    else:
        logger.error("'criticctl %s': incorrect criticctl usage did not fail"
                     % " ".join(argv))
        return []

try:
    instance.execute(["criticctl"])
except testing.NotSupported:
    # When testing with --quickstart, we can run criticctl, but we're
    # not running it as root, so this particular check is irrelevant.
    pass
except testing.virtualbox.GuestCommandError as error:
    output_lines = set(map(str.strip, error.stderr.splitlines()))
    if "ERROR: Failed to set UID = critic. Run as root?" not in output_lines:
        logger.error("Running 'criticctl' as non-root failed with unexpected "
                     "error message")
else:
    logger.error("Running 'criticctl' as non-root did not fail")

# Test -h/--help argument.
usage_lines = expect_success([],
                             ["Critic administration interface",
                              "Available commands are:"])
expect_success(["-h"],
               usage_lines)
expect_success(["--help"],
               usage_lines)

# Test --etc-dir/-e argument.
expect_success(["--etc-dir", instance.etc_dir],
               usage_lines)
expect_success(["--etc-dir=" + instance.etc_dir],
               usage_lines)
expect_success(["-e", instance.etc_dir],
               usage_lines)
expect_success(["-e" + instance.etc_dir],
               usage_lines)
lines = expect_failure(["--etc-dir", "/etc/wrong"],
                       ["ERROR: Directory is inaccessible: /etc/wrong"])
expect_failure(["-e", "/etc/wrong"],
               lines)
lines = expect_failure(["--etc-dir"],
                       ["criticctl: error: argument --etc-dir/-e: "
                        "expected one argument"])
expect_failure(["-e"],
               lines)

# Test --identity/-i argument.
expect_success(["--identity", "main"],
               usage_lines)
expect_success(["--identity=main"],
               usage_lines)
expect_success(["-i", "main"],
               usage_lines)
expect_success(["-imain"],
               usage_lines)
lines = expect_failure(["--identity", "wrong"],
                       ["ERROR: Invalid identity: wrong"])
expect_failure(["-i", "wrong"],
               lines)
lines = expect_failure(["--identity"],
                       ["criticctl: error: argument --identity/-i: "
                        "expected one argument"])
expect_failure(["-i"],
               lines)

# Test unknown arguments.
expect_failure(["-x"],
               ["criticctl: error: unrecognized arguments: -x"])
expect_failure(["--xxx"],
               ["criticctl: error: unrecognized arguments: --xxx"])

# Test unknown command.
lines = expect_failure(["foo"],
                       ["ERROR: Invalid command: foo"])
expect_failure(["-e", instance.etc_dir, "foo"],
               lines)
expect_failure(["-e" + instance.etc_dir, "foo"],
               lines)
expect_failure(["-i", "main", "foo"],
               lines)
expect_failure(["-imain", "foo"],
               lines)
expect_failure(["-e", instance.etc_dir, "-i", "main", "foo"],
               lines)
expect_failure(["-e" + instance.etc_dir, "-imain", "foo"],
               lines)
expect_failure(["-i", "main", "-e", instance.etc_dir, "foo"],
               lines)
expect_failure(["-imain", "-e" + instance.etc_dir, "foo"],
               lines)
