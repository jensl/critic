try:
    output = instance.execute(["sudo", "criticctl", "configtest"])
except testing.virtualbox.GuestCommandError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check("System configuration valid.\n", output)
