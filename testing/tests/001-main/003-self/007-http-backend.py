import os
import subprocess
import tempfile
import shutil

environ = os.environ.copy()

def git(args, cwd=None):
    argv = ["git"]
    argv.extend(args)

    logger.debug("Running: %s" % " ".join(argv))

    output = subprocess.check_output(
        argv, cwd=cwd, env=environ, stderr=subprocess.STDOUT)

    if output.strip():
        logger.debug("Output:\n%s" % output.rstrip())

work_dir = tempfile.mkdtemp()

try:
    # Set invalid password so that authentication (if required) fails.
    environ["GIT_ASKPASS"] = os.path.abspath("testing/password-invalid")

    # This should not require a password.
    try:
        git(["clone", "--quiet", "--branch", "master",
             "http://alice@%s/critic.git" % instance.hostname],
            cwd=work_dir)
    except subprocess.CalledProcessError as error:
        logger.error("'git clone' failed: %s\n%s"
                     % (str(error), error.output.rstrip()))

    # This should require a password.
    try:
        git(["push", "--quiet", "origin", "HEAD:007-http-backend-1"],
            cwd=os.path.join(work_dir, "critic"))
        logger.error("Unauthenticated push (apparently) accepted!")
    except subprocess.CalledProcessError:
        pass

    # Set valid password so that authentication succeeds.
    environ["GIT_ASKPASS"] = os.path.abspath("testing/password-testing")

    # This should require a password.
    try:
        git(["push", "--quiet", "origin", "HEAD:007-http-backend-2"],
            cwd=os.path.join(work_dir, "critic"))
    except subprocess.CalledProcessError as error:
        logger.error("'git push' failed: %s\n%s"
                     % (str(error), error.output.rstrip()))
finally:
    shutil.rmtree(work_dir)

# Same thing again, only with a repository URL without ".git" suffix.

work_dir = tempfile.mkdtemp()

try:
    # Set invalid password so that authentication (if required) fails.
    environ["GIT_ASKPASS"] = os.path.abspath("testing/password-invalid")

    # This should not require a password.
    try:
        git(["clone", "--quiet", "--branch", "master",
             "http://alice@%s/critic" % instance.hostname],
            cwd=work_dir)
    except subprocess.CalledProcessError as error:
        logger.error("'git clone' failed: %s\n%s"
                     % (str(error), error.output.rstrip()))

    # This should require a password.
    try:
        git(["push", "--quiet", "origin", "HEAD:007-http-backend-3"],
            cwd=os.path.join(work_dir, "critic"))
        logger.error("Unauthenticated push (apparently) accepted!")
    except subprocess.CalledProcessError:
        pass

    # Set valid password so that authentication succeeds.
    environ["GIT_ASKPASS"] = os.path.abspath("testing/password-testing")

    # This should require a password.
    try:
        git(["push", "--quiet", "origin", "HEAD:007-http-backend-4"],
            cwd=os.path.join(work_dir, "critic"))
    except subprocess.CalledProcessError as error:
        logger.error("'git push' failed: %s\n%s"
                     % (str(error), error.output.rstrip()))
finally:
    shutil.rmtree(work_dir)
