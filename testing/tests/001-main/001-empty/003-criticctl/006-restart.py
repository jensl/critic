try:
    output = instance.execute(["sudo", "criticctl", "restart"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    # Expected output is system dependent, so don't check.
    pass

# Check that all services are responding.  As a bonus, this also tests that the
# synchronization mechanism is working for all of them.
instance.synchronize_service("highlight")
instance.synchronize_service("changeset")
instance.synchronize_service("githook")
instance.synchronize_service("branchtracker")
instance.synchronize_service("maildelivery")
instance.synchronize_service("watchdog")
instance.synchronize_service("maintenance")

