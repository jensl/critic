import re

REVIEWS = { "giraffe": { "sha1": "5360e5d734e3b990c0dc67496c7a83f94013d01d",
                         "branch": "r/026-searchreview/giraffe",
                         "owners": ["alice"],
                         "summary": "Make sure TH element lives inside a TR element",
                         "paths": ["src/page/repositories.py"] },
            "elephant": { "sha1": "18db724faccfb2f8d04c81309feadf05b48ec9e3",
                          "branch": "r/026-searchreview/elephant",
                          "owners": ["alice", "bob"],
                          "reviewers": ["alice"],
                          "watchers": ["erin"],
                          "summary": "URL escape shortname in repository SELECT",
                          "description": """\
Before this fix, a repository shortname such as "a&b" meant that
the user would be forwarded to /branches?repository=a&b and Critic
would say "No such repository: a". Same problem existed for shortname
"a#b". Also shortname "a+b" hit the error "No such repository: a b".""",
                          "paths": ["src/resources/branches.js",
                                    "src/resources/config.js"] },
            "tiger": { "sha1": "95e52c53a4a183c9f0eada7401e1da174353e00e",
                       "branch": "r/026-searchreview/cat",
                       "owners": ["dave"],
                       "reviewers": ["dave", "erin"],
                       "summary": "Extend testing.tools.upgrade: support custom maintenance and reboot",
                       "paths": ["testing/tools/upgrade.py",
                                 "testing/virtualbox.py"] },
            "ashtray": { "sha1": "94391a18858c05b2619dfea4b58507d08d932bd3",
                         "branch": "r/026-searchreview/ashtray",
                         "owners": ["dave", "alice"],
                         "reviewers": ["dave"],
                         "summary": "Add support for installing packages in instance",
                         "description": """\
Extend the testing.tools.upgrade tool to support installing extra
packages in the instance and retake the snapshot afterwards.""",
                         "paths": ["testing/tools/upgrade.py"],
                         "dropped": True } }

FAILED = False

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

with repository.workcopy() as work:
    work.run(["remote", "add", "critic",
              "nobody@%s:/var/git/critic.git" % instance.hostname])

    for review in REVIEWS.values():
        primary_owner = review["owners"][0]

        with frontend.signin(primary_owner):
            frontend.operation(
                "savesettings",
                data={ "settings": [{ "item": "review.createViaPush",
                                      "value": True }] })

            work.run(
                ["remote", "set-url", "critic",
                 ("%s@%s:/var/git/critic.git"
                  % (primary_owner, instance.hostname))])

            output = work.run(
                ["push", "critic", "%(sha1)s:refs/heads/%(branch)s" % review])

            next_is_review_url = False

            for line in output.splitlines():
                if not line.startswith("remote:"):
                    continue
                line = line[len("remote:"):].split("\x1b", 1)[0].strip()
                if line == "Submitted review:":
                    next_is_review_url = True
                elif next_is_review_url:
                    logger.debug(line)
                    review["id"] = int(re.search(r"/r/(\d+)$", line).group(1))
                    break
            else:
                testing.expect.check("<review URL in git hook output>",
                                     "<expected content not found>")

            mailbox.pop(
                accept=[to(primary_owner),
                        about("New Review: %s" % review["summary"])])

            updatereview_data = {}

            if len(review["owners"]) > 1:
                updatereview_data["new_owners"] = review["owners"]
            if "description" in review:
                updatereview_data["new_description"] = review["description"]

            if updatereview_data:
                updatereview_data["review_id"] = review["id"]
                frontend.operation(
                    "updatereview",
                    data=updatereview_data)

            recipients = set()

            if "reviewers" in review:
                frontend.operation(
                    "addreviewfilters",
                    data={ "review_id": review["id"],
                           "filters": [{ "type": "reviewer",
                                         "user_names": review["reviewers"],
                                         "paths": ["/"] }] })
                recipients.update(review["reviewers"])

            if "watchers" in review:
                frontend.operation(
                    "addreviewfilters",
                    data={ "review_id": review["id"],
                           "filters": [{ "type": "watcher",
                                         "user_names": review["watchers"],
                                         "paths": ["/"] }] })
                recipients.update(review["watchers"])

            for username in recipients:
                if username not in review["owners"]:
                    mailbox.pop(accept=[to(username),
                                        about(r"^New\(ish\) Review:")])
                if username != primary_owner:
                    mailbox.pop(accept=[to(username),
                                        about(r"^Updated Review:")])

            if "closed" in review:
                frontend.operation(
                    "closereview",
                    data={ "review_id": review["id"] })
            if "dropped" in review:
                frontend.operation(
                    "dropreview",
                    data={ "review_id": review["id"] })

def search(query, expected):
    global FAILED

    if isinstance(query, list):
        for q in query:
            search(q, expected)
        return

    try:
        result = frontend.operation(
            "searchreview",
            data={ "query": query })
    except testing.TestFailure:
        # Continue testing instead of aborting.  The error will have
        # been logged by frontend.operation() already.
        FAILED = True
        return

    actual = dict((review["id"], review["summary"])
                  for review in result["reviews"])

    # Note: We only check that reviews we just created are included (or not) in
    # the search result.  We specifically don't check that the search result
    # doesn't contain other reviews (not created above) since that typically
    # depends on which other tests have run, on which we don't want to depend.

    for key in expected:
        expected_review = REVIEWS[key]

        if expected_review["id"] not in actual:
            logger.error("r/<%s>: not found by query %r as expected"
                         % (key, query))
            FAILED = True
        else:
            if actual[expected_review["id"]] != expected_review["summary"]:
                logger.error("r/<%s>: wrong summary %r reported"
                             % (key, actual[expected_review["id"]]))
                FAILED = True

    for key in REVIEWS.keys():
        if key not in expected:
            if REVIEWS[key]["id"] in actual:
                logger.error("r/<%s>: incorrectly found by query %r"
                             % (key, query))
                FAILED = True

def invalid(query, code, title):
    global FAILED

    try:
        frontend.operation(
            "searchreview",
            data={ "query": query },
            expect={ "status": "failure",
                     "code": code,
                     "title": title })
    except testing.TestFailure:
        # Continue testing instead of aborting.  The error will have
        # been logged by frontend.operation() already.
        FAILED = True
        return

search(query="existentialism",
       expected=[])
search(query="support",
       expected=["tiger", "ashtray"])
search(query="support for",
       expected=["ashtray"])
search(query="'support for'",
       expected=["ashtray"])
search(query='"support for"',
       expected=["ashtray"])
search(query="support owner:dave",
       expected=["tiger", "ashtray"])
search(query="support owner:alice",
       expected=["ashtray"])
search(query="support owner:bob",
       expected=[])

search(query="support installing",
       expected=["ashtray"])
search(query="'support installing'",
       expected=["ashtray"])
search(query="summary:'support installing'",
       expected=[])
search(query="description:'support installing'",
       expected=["ashtray"])

search(query="r/026-searchreview/*",
       expected=["giraffe", "elephant", "tiger", "ashtray"])
search(query=["b:r/026-searchreview/*", "branch:r/026-searchreview/*"],
       expected=["giraffe", "elephant", "tiger", "ashtray"])
search(query="path:r/026-searchreview/*",
       expected=[])
search(query="r/026-searchreview/elephant",
       expected=["elephant"])
search(query="r/026-searchreview/* upgrade.py",
       expected=["tiger", "ashtray"])
search(query="branch:r/026-searchreview/* path:upgrade.py",
       expected=["tiger", "ashtray"])
search(query=["p:upgrade.py", "path:upgrade.py"],
       expected=["tiger", "ashtray"])
search(query="branch:upgrade.py",
       expected=[])

search(query="user:alice",
       expected=["giraffe", "elephant", "ashtray"])
search(query="owner:alice",
       expected=["giraffe", "elephant", "ashtray"])
search(query="reviewer:alice",
       expected=["elephant"])

search(query="user:bob",
       expected=["elephant"])
search(query="owner:bob",
       expected=["elephant"])
search(query="reviewer:bob",
       expected=[])

search(query="user:dave",
       expected=["tiger", "ashtray"])
search(query="owner:dave",
       expected=["tiger", "ashtray"])
search(query="reviewer:dave",
       expected=["tiger", "ashtray"])

search(query=["u:erin", "user:erin"],
       expected=["elephant", "tiger"])
search(query=["o:erin", "owner:erin"],
       expected=[])
search(query=["reviewer:erin"],
       expected=["tiger"])

search(query="owner:alice reviewer:bob user:erin",
       expected=[])
search(query="reviewer:alice owner:bob",
       expected=["elephant"])

search(query=["s:open", "state:open"],
       expected=["giraffe", "elephant", "tiger"])
# It would be nice if we could make one of the reviews accepted, but doing that
# is a lot of work.  In practice, a "pending" search is almost the same as an
# "accepted" search; it's just inverted.  So we're at least quite close to
# testing an "accepted" search.
search(query=["s:pending", "state:pending"],
       expected=["giraffe", "elephant", "tiger"])
search(query=["s:accepted", "state:accepted"],
       expected=[])
# It would be nice if we could close a review too, but again, that depends on
# making a review accepted, and that's a lot of work.
search(query=["s:closed", "state:closed"],
       expected=[])
search(query=["s:dropped", "state:dropped"],
       expected=["ashtray"])

# A bit boring since there's only one repository.
search(query=["r:critic", "repo:critic", "repository:critic"],
       expected=["giraffe", "elephant", "tiger", "ashtray"])

invalid(query="overlord:admin",
        code="invalidkeyword",
        title="Invalid keyword: 'overlord'")
invalid(query="user:nosuchuser",
        code="invalidterm",
        title="No such user: 'nosuchuser'")
invalid(query="owner:nosuchuser",
        code="invalidterm",
        title="No such user: 'nosuchuser'")
invalid(query="reviewer:nosuchuser",
        code="invalidterm",
        title="No such user: 'nosuchuser'")
invalid(query="state:limbo",
        code="invalidterm",
        title="Invalid review state: 'limbo'")

if FAILED:
    raise testing.TestFailure
