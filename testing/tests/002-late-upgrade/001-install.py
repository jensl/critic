# We don't need to do anything if extension testing is not supported.
instance.check_extend(repository, pre_upgrade=True)

# We also don't need to do anything if there was no --upgrade-from.
instance.check_upgrade()

instance.start()
instance.install(repository)
