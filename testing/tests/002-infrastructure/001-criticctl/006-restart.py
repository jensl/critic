# Need a VM (full installation) to restart Critic.
# @flag full
# @flag disabled

try:
    output = instance.criticctl(["restart"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s" % error.stdout)
else:
    # Expected output is system dependent, so don't check.
    pass

# Check that all services are responding.  As a bonus, this also tests that the
# synchronization mechanism is working for all of them.
instance.synchronize_service(
    "highlight",
    "changeset",
    "githook",
    "branchtracker",
    "branchupdater",
    "maildelivery",
    "maintenance",
    "reviewupdater",
)
