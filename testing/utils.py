import re

instance = None
frontend = None

RE_REVIEW_URL = re.compile(r"^remote:\s+http://.*/r/(\d+)\s*$")

def createReviewViaPush(work, owner, commit="HEAD"):
    with frontend.signin(owner):
        frontend.operation(
            "savesettings",
            data={ "settings": [{ "item": "review.createViaPush",
                                  "value": True }] })

    remote_url = "%s@%s:/var/git/critic.git" % (owner, instance.hostname)
    output = work.run(["push", remote_url, "HEAD"], TERM="dumb")
    for line in output.splitlines():
        match = RE_REVIEW_URL.match(line)
        if match:
            return int(match.group(1))
    else:
        testing.expect.check("<review URL in 'git push' output>",
                             "<no review URL found>")
