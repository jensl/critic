instance.unittest("api.changeset", ["pre"])

instance.synchronize_service("changeset") # wait for changeset creation to finish

instance.unittest("api.changeset", ["post"])
