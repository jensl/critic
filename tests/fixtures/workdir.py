import os
import pytest
import tempfile


@pytest.fixture(scope="session")
def workdir():
    with tempfile.TemporaryDirectory() as workdir:
        os.mkdir(os.path.join(workdir, "scripts"))
        with open(
            os.path.join(workdir, "scripts", "git-askpass.sh"), "w"
        ) as git_askpass:
            print("#!/bin/sh\necho $GIT_PASSWORD\n", file=git_askpass)
        yield workdir
