instance.unittest("api.filediff", ["pre1"])

instance.synchronize_service("changeset") # wait for changeset creation to finish

instance.unittest("api.filediff", ["pre2"])

instance.synchronize_service("highlight") # wait for syntax highlighting to finish

instance.unittest("api.filediff", ["post"])
