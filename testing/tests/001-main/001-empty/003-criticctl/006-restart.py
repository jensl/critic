try:
    output = instance.execute(["sudo", "criticctl", "restart"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    # Expected output is system dependent, so don't check.
    pass
