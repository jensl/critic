import os

FILENAME = "020-reviewrebase.txt"
FILENAME_BASE = "020-reviewrebase.base.txt"

NONSENSE = """\
Lorem ipsum dolor sit amet, consectetur adipiscing
elit. Donec ut enim sit amet purus ultricies
lobortis. Pellentesque nisi arcu, convallis sed purus sed,
semper ultrices velit. Ut egestas lorem tortor, vitae
lacinia lorem consectetur nec. Integer tempor ornare ipsum
at viverra. Curabitur nec orci mollis, lacinia sapien eget,
ultricies ipsum. Curabitur a libero tortor. Curabitur
volutpat lacinia erat, ac suscipit enim dignissim nec."""

def lines(*args):
    return "\n".join((line.upper() if index in args else line)
                     for index, line in enumerate(NONSENSE.splitlines()))

def to(name):
    return testing.mailbox.ToRecipient("%s@example.org" % name)

def about(subject):
    return testing.mailbox.WithSubject(subject)

SETTINGS = { "review.createViaPush": True,
             "email.subjectLine.updatedReview.reviewRebased":
                 "Rebased Review: %(summary)s" }

work = repository.workcopy()
settings = testing.utils.settings("alice", SETTINGS)
signin = frontend.signin("alice")
reviews = []

with work, settings, signin:
    work.run(["remote", "add", "critic",
              "alice@%s:/var/git/critic.git" % instance.hostname])

    def write(*args, **kwargs):
        """Write the file<tm>, optionally with lines upper-cased."""
        filename = kwargs.get("filename", FILENAME)
        with open(os.path.join(work.path, filename), "w") as target:
            print >>target, lines(*args)

    def commit(message_or_ref="HEAD", generate=None, *args, **kwargs):
        """If called with two or more arguments, create a commit and return,
           otherwise return commit referenced by first argument."""
        if generate is not None:
            generate(*args, **kwargs)
            work.run(["add", kwargs.get("filename", FILENAME)])
            work.run(["commit", "-m", message_or_ref])
            message_or_ref = "HEAD"

        oneline = work.run(["log", "--no-abbrev", "--pretty=oneline", "-1",
                            message_or_ref])
        sha1, summary = oneline.strip().split(" ", 1)

        return { "sha1": sha1, "summary": summary }

    def expectmail(title):
        review = reviews[-1]
        mailbox.pop(accept=[to("alice"),
                            about("%s: %s" % (title, review["summary"]))])

    def expecthead(expected):
        """Check that the review branch in Critic's repository is where we want
           it to be."""
        review = reviews[-1]
        actual = work.run(["ls-remote", "critic", review["branch"]]).split()[0]
        testing.expect.check(expected["sha1"], actual)

    def createreview(commits):
        """Create a review of the specified commits."""
        index = len(reviews) + 1
        branch = "020-reviewrebase/%d" % index
        summary = "020-reviewrebase, test %d" % index
        work.run(["push", "critic", "%s:refs/heads/%s" % (commits[-1]["sha1"],
                                                          branch)])
        result = frontend.operation(
            "submitreview",
            data={ "repository": "critic",
                   "commit_sha1s": [commit["sha1"] for commit in commits],
                   "branch": "r/" + branch,
                   "summary": summary })
        reviews.append({ "id": result["review_id"],
                         "branch": "r/" + branch,
                         "summary": summary })
        expectmail("New Review")

    def push(new_head, force=False):
        """Push specified commit to the review branch in Critic's repository,
           optionally forced."""
        review = reviews[-1]
        args = ["push"]
        if force:
            args.append("-f")
        args.extend(["critic", "%s:refs/heads/%s" % (new_head["sha1"],
                                                     review["branch"])])
        work.run(args)
        expecthead(new_head)

    def moverebase(new_upstream, new_head):
        """Perform a move rebase."""
        review = reviews[-1]
        work.run(["reset", "--hard", new_head["sha1"]])
        frontend.operation(
            "preparerebase",
            data={ "review_id": review["id"],
                   "new_upstream": new_upstream["sha1"] })
        push(new_head, force=True)
        expectmail("Rebased Review")

    def historyrewrite(new_head):
        """Perform a history rewrite rebase."""
        review = reviews[-1]
        work.run(["reset", "--hard", new_head["sha1"]])
        frontend.operation(
            "preparerebase",
            data={ "review_id": review["id"] })
        push(new_head, force=True)
        expectmail("Rebased Review")

    def expectlog(expected):
        """Fetch the review front-page and check that the commit log contains
           the expected lines.

           Also fetch a /showcommit page whose 'Squashed History' log lists
           everything in the review and check that it contains the same lines
           too."""

        expected = [(item if isinstance(item, str) else item["summary"])
                    for item in expected]

        def checklog(document):
            with_class = testing.expect.with_class
            actual = []
            for tr in document.findAll("tr"):
                if not tr.has_key("class"):
                    continue
                classes = tr["class"].split()
                if "commit" in classes:
                    td = tr.find("td", attrs=with_class("summary"))
                    a = td.find("a", attrs=with_class("commit"))
                    actual.append(a.string)
                elif "rebase" in classes:
                    td = tr.find("td")
                    if td.contents[0].startswith("Branch rebased"):
                        a = td.find("a")
                        sha1 = a["href"].split("/")[-1]
                        actual.append("rebased onto " + sha1)
                    elif td.contents[0].startswith("History rewritten"):
                        actual.append("history rewritten")
            testing.expect.check(expected, actual)

        review = reviews[-1]

        frontend.page(
            "r/%d" % review["id"],
            expect={ "log": checklog })
        frontend.page(
            "showcommit",
            params={ "review": review["id"],
                     "filter": "files",
                     "file": FILENAME },
            expect={ "log": checklog })

    def revertrebase():
        """Revert the most recent rebase."""
        review = reviews[-1]
        document = frontend.page("r/%d" % review["id"])
        for a in document.findAll("a"):
            if a.string == "[revert]":
                def revertRebase(rebase_id):
                    return rebase_id
                rebase_id = eval(a["href"].split(":", 1)[1])
                break
        else:
            logger.error("No [revert] link found!")
        frontend.operation(
            "revertrebase",
            data={ "review_id": review["id"],
                   "rebase_id": rebase_id })

    start_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    # TEST #1: Create a review with three commits, then history rewrite so that
    # the branch points to the first commit (i.e. remove the second and third
    # commit.)  Then push another pair of commits, and history rewrite back to
    # the first commit again.

    work.run(["checkout", "-b", "020-reviewrebase-1", start_sha1])
    commits = [commit("Test #1, commit 1", write),
               commit("Test #1, commit 2", write, 4, 5),
               commit("Test #1, commit 3", write)]
    createreview(commits)
    historyrewrite(commits[0])
    expectlog(["history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    commits.extend([commit("Test #1, commit 4", write, 3, 4, 5),
                    commit("Test #1, commit 5", write, 4, 5),
                    commit("Test #1, commit 6", write)])
    push(commits[-1])
    expectmail("Updated Review")
    expectlog([commits[5],
               commits[4],
               commits[3],
               "history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    historyrewrite(commits[0])
    expectlog(["history rewritten",
               commits[5],
               commits[4],
               commits[3],
               "history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    revertrebase()
    expectlog([commits[5],
               commits[4],
               commits[3],
               "history rewritten",
               commits[2],
               commits[1],
               commits[0]])

    # Random extra check for crash fixed in http://critic-review.org/r/207:
    # Use the [partial] filter to look at the two last commits in the review.
    # We're only interested in checking that the page loads successfully.
    frontend.page(
        "showcommit",
        params={ "from": commits[3]["sha1"],
                 "to": commits[5]["sha1"],
                 "review": reviews[-1]["id"],
                 "filter": "files",
                 "file": FILENAME })

    # TEST #2: First, set up two different commits that we'll be basing our
    # review branch on.  Then create a review with three commits, move rebase
    # it (ff), rewrite the history, and move rebase it (non-ff) again.

    work.run(["checkout", "-b", "020-reviewrebase-2-base", start_sha1])
    base_commits = [commit("Test #2 base, commit 1", write),
                    commit("Test #2 base, commit 2", write, 0)]
    work.run(["push", "critic", "020-reviewrebase-2-base"])
    work.run(["checkout", "-b", "020-reviewrebase-2", base_commits[0]["sha1"]])
    commits = [commit("Test #2, commit 1", write, 5),
               commit("Test #2, commit 2", write, 5, 6),
               commit("Test #2, commit 3", write, 5, 6, 7)]
    createreview(commits)
    work.run(["reset", "--hard", base_commits[1]["sha1"]])
    commits.extend([commit("Test #2, commit 4", write, 0, 5),
                    commit("Test #2, commit 5", write, 0, 5, 6),
                    commit("Test #2, commit 6", write, 0, 5, 6, 7)])
    moverebase(base_commits[1], commits[-1])
    expectlog(["rebased onto " + base_commits[1]["sha1"],
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[1]["sha1"]])
    commits.append(commit("Test #2, commit 7", write, 0, 5, 6, 7))
    historyrewrite(commits[-1])
    expectlog(["history rewritten",
               "rebased onto " + base_commits[1]["sha1"],
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[0]["sha1"]])
    commits.append(commit("Test #2, commit 8", write, 5, 6, 7))
    moverebase(base_commits[0], commits[-1])
    expectlog(["rebased onto " + base_commits[0]["sha1"],
               "history rewritten",
               "rebased onto " + base_commits[1]["sha1"],
               commits[2],
               commits[1],
               commits[0]])

    # TEST #3: Like test #2, but the base commits have changes that trigger
    # "conflicts" and thus equivalent merge commits.

    work.run(["checkout", "-b", "020-reviewrebase-3-base", start_sha1])
    base_commits = [commit("Test #3 base, commit 1", write),
                    commit("Test #3 base, commit 2", write, 2)]
    work.run(["push", "critic", "020-reviewrebase-3-base"])
    work.run(["checkout", "-b", "020-reviewrebase-3", base_commits[0]["sha1"]])
    commits = [commit("Test #3, commit 1", write, 5),
               commit("Test #3, commit 2", write, 5, 6),
               commit("Test #3, commit 3", write, 5, 6, 7)]
    createreview(commits)
    work.run(["reset", "--hard", base_commits[1]["sha1"]])
    commits.extend([commit("Test #3, commit 4", write, 2, 5),
                    commit("Test #3, commit 5", write, 2, 5, 6),
                    commit("Test #3, commit 6", write, 2, 5, 6, 7)])
    moverebase(base_commits[1], commits[-1])
    expectmail("Updated Review")
    expectlog(["rebased onto " + base_commits[1]["sha1"],
               "Merge commit '%s' into %s" % (base_commits[1]["sha1"],
                                              reviews[-1]["branch"]),
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[1]["sha1"]])
    commits.append(commit("Test #3, commit 7", write, 2, 5, 6, 7))
    historyrewrite(commits[-1])
    expectlog(["history rewritten",
               "rebased onto " + base_commits[1]["sha1"],
               "Merge commit '%s' into %s" % (base_commits[1]["sha1"],
                                              reviews[-1]["branch"]),
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[0]["sha1"]])
    commits.append(commit("Test #3, commit 8", write, 5, 6, 7))
    moverebase(base_commits[0], commits[-1])
    expectlog(["rebased onto " + base_commits[0]["sha1"],
               "history rewritten",
               "rebased onto " + base_commits[1]["sha1"],
               "Merge commit '%s' into %s" % (base_commits[1]["sha1"],
                                              reviews[-1]["branch"]),
               commits[2],
               commits[1],
               commits[0]])

    # TEST #4: Create a review with three commits based on master~2, then merge
    # master~1 into the review, and then rebase the review onto master.

    work.run(["fetch", "critic", "refs/heads/master"])
    base_commits = [commit("FETCH_HEAD~2"),
                    commit("FETCH_HEAD~1"),
                    commit("FETCH_HEAD")]
    work.run(["checkout", "-b", "020-reviewrebase-4-1",
              base_commits[0]["sha1"]])
    commits = [commit("Test #4, commit 1", write, 7),
               commit("Test #4, commit 2", write, 6, 7),
               commit("Test #4, commit 3", write, 5, 6, 7)]
    createreview(commits)
    work.run(["checkout", "-b", "020-reviewrebase-4-2",
              base_commits[1]["sha1"]])
    work.run(["merge", "020-reviewrebase-4-1"])
    commits.append(commit())
    push(commits[-1])
    expectmail("Updated Review")
    work.run(["reset", "--hard", base_commits[2]["sha1"]])
    commits.extend([commit("Test #4, commit 4", write, 7),
                    commit("Test #4, commit 5", write, 6, 7),
                    commit("Test #4, commit 6", write, 5, 6, 7)])
    moverebase(base_commits[2], commits[-1])
    expectlog(["rebased onto " + base_commits[2]["sha1"],
               commits[3],
               commits[2],
               commits[1],
               commits[0]])

    # TEST #5: First, set up two different commits that we'll be basing our
    # review branch on.  Then create a review with three commits, then history
    # rewrite so that the branch points to the first commit (i.e. remove the
    # second and third commit.)  Then non-ff move-rebase the review.

    work.run(["checkout", "-b", "020-reviewrebase-5-base", start_sha1])
    base_commits = [commit("Test #5 base, commit 1", write, filename=FILENAME_BASE),
                    commit("Test #5 base, commit 2", write, 0, filename=FILENAME_BASE)]
    work.run(["push", "critic", "020-reviewrebase-5-base"])
    work.run(["checkout", "-b", "020-reviewrebase-5", base_commits[1]["sha1"]])
    commits = [commit("Test #5, commit 1", write, 4),
               commit("Test #5, commit 2", write, 4, 5),
               commit("Test #5, commit 3", write, 4)]
    createreview(commits)
    historyrewrite(commits[0])
    expectlog(["history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[0]["sha1"]])
    commits.append(commit("Test #5, commit 4", write, 4))
    moverebase(base_commits[0], commits[-1])
    expectlog(["rebased onto " + base_commits[0]["sha1"],
               "history rewritten",
               commits[2],
               commits[1],
               commits[0]])

    # TEST #6: Like test #5, but we revert the rebases afterwards.

    work.run(["checkout", "-b", "020-reviewrebase-6-base", start_sha1])
    base_commits = [commit("Test #6 base, commit 1", write, filename=FILENAME_BASE),
                    commit("Test #6 base, commit 2", write, 0, filename=FILENAME_BASE)]
    work.run(["push", "critic", "020-reviewrebase-6-base"])
    work.run(["checkout", "-b", "020-reviewrebase-6", base_commits[1]["sha1"]])
    commits = [commit("Test #6, commit 1", write, 4),
               commit("Test #6, commit 2", write, 4, 5),
               commit("Test #6, commit 3", write, 4)]
    createreview(commits)
    historyrewrite(commits[0])
    expectlog(["history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    work.run(["reset", "--hard", base_commits[0]["sha1"]])
    commits.append(commit("Test #6, commit 4", write, 4))
    moverebase(base_commits[0], commits[-1])
    expectlog(["rebased onto " + base_commits[0]["sha1"],
               "history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    revertrebase()
    expectlog(["history rewritten",
               commits[2],
               commits[1],
               commits[0]])
    revertrebase()
    expectlog([commits[2],
               commits[1],
               commits[0]])
