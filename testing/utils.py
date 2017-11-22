import contextlib
import os
import re

instance = None
frontend = None

RE_REVIEW_URL = re.compile(r"^remote:\s+http://.*/r/(\d+)\s*$")


@contextlib.contextmanager
def settings(user, settings, repository=None):
    data = {
        "settings": [{"item": item, "value": value} for item, value in settings.items()]
    }
    if repository:
        data["repository"] = repository

    # Set requested settings.
    with frontend.signin(user):
        frontend.operation("savesettings", data=data)

    try:
        yield
    finally:
        data = {"settings": [{"item": item} for item, value in settings.items()]}
        if repository:
            data["repository"] = repository

        # Reset settings back to the default.
        with frontend.signin(user):
            frontend.operation("savesettings", data=data)


@contextlib.contextmanager
def access_token(user, profile):
    with frontend.signin(user):
        access_token = frontend.json(
            "users/me/accesstokens",
            post={"title": "by testing.utils.access_token()", "profile": profile},
            expect={
                "id": int,
                "access_type": "user",
                "user": instance.userid(user),
                "title": "by testing.utils.access_token()",
                "part1": str,
                "part2": str,
                "profile": dict,
            },
        )

    try:
        yield access_token
    finally:
        with frontend.signin(user):
            frontend.json(
                "accesstokens/%d" % access_token["id"],
                delete=True,
                expected_http_status=204,
            )


@contextlib.contextmanager
def environment(**kwargs):
    previous = {key: os.environ.get(key) for key in kwargs}
    for key, value in kwargs.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield os.environ
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def createReviewViaPush(work, owner, commit=None, branch_name=None):
    import testing

    with settings(owner, {"review.pushAutoPublishLimit": 1}):
        remote_url = instance.repository_url(owner)
        if commit is not None and branch_name is not None:
            refspec = "%s:refs/heads/%s" % (commit, branch_name)
        else:
            refspec = "HEAD"
        output = work.run(["push", remote_url, refspec], TERM="dumb")
        for line in output.splitlines():
            match = RE_REVIEW_URL.match(line)
            if match:
                return int(match.group(1))
        else:
            testing.expect.check(
                "<review URL in 'git push' output>", "<no review URL found>"
            )


class UnknownValue:
    class NotDetermined:
        pass

    def __init__(self):
        self.__value = UnknownValue.NotDetermined

    def __eq__(self, other):
        if self.__value is UnknownValue.NotDetermined:
            self.__value = other
        return self.__value == other
