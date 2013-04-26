import json

from BeautifulSoup import Comment

def check_injected(key, expected):
    def check(document):
        comments = document.findAll(text=lambda text: isinstance(text, Comment))

        for comment in comments:
            if comment.strip().startswith("[alice/TestExtension] Extension error:"):
                logger.error(comment.strip())
                return

        for script in document.findAll("script"):
            if script.has_key("src"):
                src = script["src"]
                if src.startswith("data:text/javascript,var %s=" % key) \
                        and src[-1] == ";":
                    injected = src[len("data:text/javascript,var %s=" % key):-1]
                    break
        else:
            testing.expect.check("<injected script>",
                                 "<expected content not found>")

        try:
            actual = json.loads(injected)
        except ValueError:
            testing.expect.check("<valid json>", repr(injected))
        else:
            testing.expect.check(expected, actual)

    return check

def check_not_injected(key):
    def check(document):
        comments = document.findAll(text=lambda text: isinstance(text, Comment))

        for comment in comments:
            if comment.strip().startswith("[alice/TestExtension] Extension error:"):
                logger.error(comment.strip())
                return

        for script in document.findAll("script"):
            if script.has_key("src"):
                src = script["src"]
                if src.startswith("data:text/javascript,var %s=" % key) \
                        and src[-1] == ";":
                    testing.expect.check("<no injected script>",
                                         "<injected script found>")
                    break

    return check

with frontend.signin("alice"):
    frontend.page(
        "home",
        expect={ "injected": check_injected(
                "injected",
                ["home", None]) })

    frontend.page(
        "home?foo=bar",
        expect={ "injected": check_injected(
                "injected",
                ["home", { "raw": "foo=bar",
                           "params": { "foo": "bar" }}]) })

    frontend.page(
        "home?foo=bar&x=10&y=20",
        expect={ "injected": check_injected(
                "injected",
                ["home", { "raw": "foo=bar&x=10&y=20",
                           "params": { "foo": "bar",
                                       "x": "10",
                                       "y": "20" }}]) })

    sha1 = repository.run(["rev-parse", "master"]).strip()

    frontend.page(
        "critic/master",
        expect={ "showcommitShort": check_injected(
                "showcommitShort",
                ["critic/master", None]),
                 "showcommitLong": check_injected(
                "showcommitLong",
                ["showcommit", { "raw": "repository=1&sha1=" + sha1,
                                 "params": { "repository": "1",
                                             "sha1": sha1 }}]) })

    frontend.page(
        "showcommit?repository=critic&sha1=master",
        expect={ "showcommitShort": check_not_injected(
                "showcommitShort"),
                "showcommitLong": check_injected(
                "showcommitLong",
                ["showcommit", { "raw": "repository=critic&sha1=master",
                                 "params": { "repository": "critic",
                                             "sha1": "master" }}]) })

# Verify that Alice's extension install doesn't affect Bob.
with frontend.signin("bob"):
    frontend.page(
        "home",
        expect={ "injected": check_not_injected("injected") })
