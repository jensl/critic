instance.unittest("api.filechange", ["pre"])

instance.synchronize_service("changeset") # wait for changeset creation to finish

instance.unittest("api.filechange", ["post"])
