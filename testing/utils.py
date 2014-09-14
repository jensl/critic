import re
import contextlib

instance = None
frontend = None

RE_REVIEW_URL = re.compile(r"^remote:\s+http://.*/r/(\d+)\s*$")

@contextlib.contextmanager
def settings(user, settings, repository=None):
    data = { "settings": [{ "item": item, "value": value }
                          for item, value in settings.items()] }
    if repository:
        data["repository"] = repository

    # Set requested settings.
    with frontend.signin(user):
        frontend.operation("savesettings", data=data)

    try:
        yield
    finally:
        data = { "settings": [{ "item": item }
                              for item, value in settings.items()] }
        if repository:
            data["repository"] = repository

        # Reset settings back to the default.
        with frontend.signin(user):
            frontend.operation("savesettings", data=data)

def createReviewViaPush(work, owner, commit="HEAD"):
    with settings(owner, { "review.createViaPush": True }):
        remote_url = instance.repository_url(owner)
        output = work.run(["push", remote_url, "HEAD"], TERM="dumb")
        for line in output.splitlines():
            match = RE_REVIEW_URL.match(line)
            if match:
                return int(match.group(1))
        else:
            testing.expect.check("<review URL in 'git push' output>",
                                 "<no review URL found>")
