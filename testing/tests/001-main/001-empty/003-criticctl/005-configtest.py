try:
    output = instance.criticctl(["configtest"])
except testing.CriticctlError as error:
    logger.error("correct criticctl usage failed:\n%s"
                 % error.stdout)
else:
    testing.expect.check("System configuration valid.\n", output)
