# @flag uninstall

# Uninstall Critic.
instance.uninstall()

# Delete the repository clone (the install() call recreates it.)
instance.execute(["rm", "-rf", "critic"])

# Install (and upgrade, optionally) Critic with the default arguments.
instance.install(repository, other_cwd=True)
instance.upgrade()
