import os

FILENAME = "033-propagation-vs-rebase.txt"
FILENAME_BASE = "033-propagation-vs-rebase.base.txt"

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
    REMOTE_URL = instance.repository_url("alice")

    def write(*args, **kwargs):
        """Write the file<tm>, optionally with lines upper-cased."""
        filename = kwargs.get("filename", FILENAME)
        with open(os.path.join(work.path, filename), "w") as target:
            print >>target, lines(*args)

    def commit(message, *args, **kwargs):
        """Create a commit and return its SHA-1"""
        write(*args, **kwargs)
        work.run(["add", kwargs.get("filename", FILENAME)])
        work.run(["commit", "-m", message])
        return work.run(["rev-parse", "HEAD"]).strip()

    def expectmail(title):
        review = reviews[-1]
        mailbox.pop(accept=[to("alice"),
                            about("%s: %s" % (title, review["summary"]))])

    def expecthead(expected):
        """Check that the review branch in Critic's repository is where we want
           it to be."""
        review = reviews[-1]
        actual = work.run(["ls-remote", REMOTE_URL, review["branch"]]).split()[0]
        testing.expect.check(expected, actual)

    def createreview(commits):
        """Create a review of the specified commits."""
        index = len(reviews) + 1
        branch = "033-propagation-vs-rebase/%d" % index
        summary = "033-propagation-vs-rebase, test %d" % index
        work.run(["push", REMOTE_URL, "%s:refs/heads/%s" % (commits[-1],
                                                            branch)])
        result = frontend.operation(
            "submitreview",
            data={ "repository": "critic",
                   "commit_sha1s": [sha1 for sha1 in commits],
                   "branch": "r/" + branch,
                   "frombranch": branch,
                   "summary": summary })
        reviews.append({ "id": result["review_id"],
                         "branch": "r/" + branch,
                         "summary": summary })
        instance.synchronize_service("reviewupdater")
        expectmail("New Review")

    def push(new_head, force=False):
        """Push specified commit to the review branch in Critic's repository,
           optionally forced."""
        review = reviews[-1]
        args = ["push"]
        if force:
            args.append("-f")
        args.extend([REMOTE_URL, "%s:refs/heads/%s" % (new_head,
                                                       review["branch"])])
        work.run(args)
        expecthead(new_head)

    def moverebase(new_upstream, new_head):
        """Perform a move rebase."""
        review = reviews[-1]
        work.run(["reset", "--hard", new_head])
        frontend.operation(
            "preparerebase",
            data={ "review_id": review["id"],
                   "new_upstream": new_upstream })
        push(new_head, force=True)
        expectmail("Rebased Review")

    def historyrewrite(new_head):
        """Perform a history rewrite rebase."""
        review = reviews[-1]
        work.run(["reset", "--hard", new_head])
        frontend.operation(
            "preparerebase",
            data={ "review_id": review["id"] })
        push(new_head, force=True)
        expectmail("Rebased Review")

    def createcomment(parent_sha1, child_sha1, offset, count, verdict):
        frontend.operation(
            "validatecommentchain",
            data={ "review_id": reviews[-1]["id"],
                   "origin": "new",
                   "parent_sha1": parent_sha1,
                   "child_sha1": child_sha1,
                   "file_path": FILENAME,
                   "offset": offset,
                   "count": count },
            expect={ "verdict": verdict })
        frontend.operation(
            "createcommentchain",
            data={ "review_id": reviews[-1]["id"],
                   "chain_type": "issue",
                   "file_context": {
                       "origin": "new",
                       "parent_sha1": parent_sha1,
                       "child_sha1": child_sha1,
                       "file_path": FILENAME,
                       "offset": offset,
                       "count": count },
                   "text": ("Issue at lines %d-%d"
                            % (offset, offset + count - 1)) })

    start_sha1 = work.run(["rev-parse", "HEAD"]).strip()

    # TEST #1: Create a review with one commit, then do a fast-forward move
    # rebase, and then create some comments in the diff of the original,
    # pre-rebase commit.

    work.run(["checkout", "-b", "033-propagation-vs-rebase-base", start_sha1])
    base_commits = [commit("Base commit 1"),
                    commit("Base commit 2", 0),
                    commit("Base commit 3", 0, 1)]
    work.run(["push", REMOTE_URL, "HEAD"])

    work.run(["checkout", "-b", "033-propagation-vs-rebase-1", base_commits[0]])
    original_commits = [commit("Test #1, commit 1", 6, 7)]
    createreview(original_commits)
    work.run(["reset", "--hard", base_commits[2]])
    rebased_commits = [commit("Test #1, commit 1 (rebased)", 0, 1, 6, 7)]
    moverebase(base_commits[2], rebased_commits[0])

    # Lines modified in the rebase.
    createcomment(base_commits[0], original_commits[0], 1, 2, "modified")

    # Lines not modified at all.
    createcomment(base_commits[0], original_commits[0], 4, 2, "transferred")

    # Lines modified in the review (but not in the rebase).
    createcomment(base_commits[0], original_commits[0], 7, 2, "transferred")

    # TEST #2: Create a review with one commit, then do a non-fast-forward move
    # rebase, and then create some comments in the diff of the original,
    # pre-rebase commit.

    work.run(["checkout", "-b", "033-propagation-vs-rebase-2", base_commits[2]])
    original_commits = [commit("Test #2, commit 1", 0, 1, 6, 7)]
    createreview(original_commits)
    work.run(["reset", "--hard", base_commits[0]])
    rebased_commits = [commit("Test #2, commit 1 (rebased)", 6, 7)]
    moverebase(base_commits[0], rebased_commits[0])

    # Lines modified in the rebase.
    createcomment(base_commits[0], original_commits[0], 1, 2, "modified")

    # Lines not modified at all.
    createcomment(base_commits[0], original_commits[0], 4, 2, "transferred")

    # Lines modified in the review (but not in the rebase).
    createcomment(base_commits[0], original_commits[0], 7, 2, "transferred")
