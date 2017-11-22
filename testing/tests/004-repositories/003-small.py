# @user alice

import os
import tempfile

# Add a third repository, that is (almost) empty and is quick to create. This
# speeds up running of tests that don't need a bigger repository.
instance.criticctl(["addrepository", "--name", "small", "--path", "small"])

url = instance.repository_url("alice", repository="small")

with tempfile.TemporaryDirectory() as tempdir:
    repository.run(["init", "small"], cwd=tempdir)

    small = os.path.join(tempdir, "small")

    with open(os.path.join(small, "README.txt"), "w") as readme:
        print("This is a small repository.", file=readme)

    repository.run(["add", "README.txt"], cwd=small)
    repository.run(["commit", "-m", "Initial commit"], cwd=small)
    repository.run(["push", url, "HEAD:refs/heads/master"], cwd=small)

instance.register_repository(frontend.json("repositories", params={"name": "small"}))
