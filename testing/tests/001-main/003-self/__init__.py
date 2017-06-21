import os

class Review(object):
    def __init__(self, workcopy, as_user, work_branch_name):
        self.workcopy = workcopy
        self.work_branch_name = work_branch_name
        self.review_branch_name = "r/" + work_branch_name
        self.summary = work_branch_name
        self.as_user = as_user
        self.sha1s = []
        self.reference_commits = 0
        self.pushed_commits = 0
        self.files = {}
        self.review_id = None
        self.filters = []
        self.users = set([as_user])

        self.workcopy.run(["checkout", "-b", self.work_branch_name])

    class File(object):
        def __init__(self, filename):
            self.filename = filename
            self.content = None

        def write(self, path):
            filename = os.path.join(path, self.filename)
            if self.content is None:
                if os.path.isfile(filename):
                    os.unlink(filename)
            else:
                if isinstance(self.content, list):
                    content = "\n".join(self.content) + "\n"
                else:
                    content = self.content
                if not os.path.isdir(os.path.dirname(filename)):
                    os.makedirs(os.path.dirname(filename))
                with open(filename, "w") as fileobj:
                    fileobj.write(content)

    def addFile(self, **files):
        for key, filename in files.items():
            self.files[key] = Review.File(filename)

    def getFilename(self, key):
        return self.files[key].filename

    def getFileId(self, key):
        result = frontend.json(
            "files",
            params={
                "path": self.files[key].filename,
            },
            expect={
                "id": int,
                "path": self.files[key].filename,
            })
        return result["id"]

    def commit(self, message, **files):
        if files.pop("reference", False):
            assert len(self.sha1s) == self.reference_commits
            self.reference_commits += 1
        for key, content in files.items():
            self.files[key].content = content
        for file_ in self.files.values():
            file_.write(self.workcopy.path)
            self.workcopy.run(["add", file_.filename])
        self.workcopy.run(["commit", "-m", message])
        self.sha1s.append(self.workcopy.run(["rev-parse", "HEAD"]).strip())

    def addFilter(self, username, filter_type, path):
        assert filter_type in ("reviewer", "watcher")
        self.users.add(username)
        self.filters.append({
            "username": username,
            "type": filter_type,
            "path": path
        })

    def submit(self):
        assert len(self.sha1s) > self.reference_commits

        self.workcopy.run(
            ["push", instance.repository_url(self.as_user), "HEAD"])
        self.pushed_commits = len(self.sha1s)

        with frontend.signin(self.as_user):
            result = frontend.operation(
                "submitreview",
                data={
                    "repository": "critic",
                    "branch": self.review_branch_name,
                    "summary": self.work_branch_name,
                    "commit_sha1s": self.sha1s[self.reference_commits:],
                    "reviewfilters": self.filters,
                    "frombranch": self.work_branch_name,
                })

        self.id = result["review_id"]

        instance.synchronize_service("reviewupdater")

        for username in self.users:
            mailbox.pop(accept=[
                testing.mailbox.ToRecipient(username + "@example.org"),
                testing.mailbox.WithSubject("New Review: " + self.summary)
            ])

    def push(self):
        assert self.review_id is not None, "call review.submit() first!"

        self.workcopy.run(
            ["push", instance.repository_url(self.as_user),
             "HEAD:%s" % self.review_branch_name])

        for username in self.users:
            mailbox.pop(accept=[
                testing.mailbox.ToRecipient(username + "@example.org"),
                testing.mailbox.WithSubject("Updated Review: " + self.summary)
            ])
