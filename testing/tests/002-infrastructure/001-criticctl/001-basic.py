import re


def expect_success(argv, expected_output_lines=[]):
    try:
        output = instance.criticctl(argv)
    except testing.CriticctlError as error:
        logger.error(
            "'criticctl %s': correct criticctl usage failed:\n%s"
            % (" ".join(argv), error.stdout)
        )
        return []
    else:
        output_lines = set(map(str.strip, output.splitlines()))
        for expected_line in expected_output_lines:
            if isinstance(expected_line, str):
                found = expected_line in output_lines
            else:
                found = any(expected_line.match(line) for line in output_lines)
            if not found:
                logger.error(
                    "'%s': Expected output line not found:\n  %r"
                    % (" ".join(argv), expected_line)
                )
        return output_lines


def expect_failure(argv, expected_output_lines=[]):
    try:
        instance.criticctl(argv)
    except testing.CriticctlError as error:
        output_lines = set(map(str.strip, error.stderr.splitlines()))
        for expected_line in expected_output_lines:
            if isinstance(expected_line, str):
                found = expected_line in output_lines
            else:
                found = any(expected_line.match(line) for line in output_lines)
            if not found:
                logger.error(
                    "'%s': Expected output line not found:\n  %r"
                    % (" ".join(argv), expected_line)
                )
        return output_lines
    else:
        logger.error(
            "'criticctl %s': incorrect criticctl usage did not fail" % " ".join(argv)
        )
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
        logger.error(
            "Running 'criticctl' as non-root failed with unexpected " "error message"
        )
else:
    logger.error("Running 'criticctl' as non-root did not fail")

# Test -h/--help argument.
usage_lines = expect_success(
    [],
    ["Critic administration interface", re.compile(r"COMMAND\s+Command to perform.")],
)

expect_success(["-h"], usage_lines)
expect_success(["--help"], usage_lines)

# Test unknown arguments.
expect_failure(["-x"], ["criticctl: error: unrecognized arguments: -x"])
expect_failure(["--xxx"], ["criticctl: error: unrecognized arguments: --xxx"])

# Test unknown command.
expect_failure(
    ["foo"], [re.compile("criticctl: error: argument COMMAND: invalid choice: 'foo'.*")]
)
