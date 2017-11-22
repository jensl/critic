# @flag clean

import os
import re


def NewReviewMail(review_id):
    review = frontend.json(
        "reviews/%d" % review_id,
        params={
            "fields[reviews]": "summary,partitions",
            "fields[commits]": "id,sha1",
            "include": "commits",
        },
        expect={
            "is_partial": True,
            "summary": str,
            "partitions": [{"commits": list, "rebase": None}],
            "linked": {"commits": list},
        },
    )

    class NewReviewMail(object):
        def __init__(self, mail):
            testing.expect.equal(
                "New Review: %s" % review["summary"], mail.header("Subject")
            )

            included_commits = {
                commit["id"]: commit["sha1"] for commit in review["linked"]["commits"]
            }
            expected_commits = [
                included_commits[commit_id]
                for commit_id in review["partitions"][0]["commits"]
            ]
            actual_commits = []

            for line in mail.lines:
                match = re.match("^Commit: ([0-9a-f]{40})$", line)
                if match:
                    sha1, = match.groups()
                    actual_commits.append(sha1)

            testing.expect.equal(
                expected_commits,
                actual_commits,
                message="%s to <%s>" % (mail.subject, mail.recipient),
            )

    return NewReviewMail


def mail_to(username, wrapper):
    return wrapper(
        mailbox.pop(accept=testing.mailbox.ToRecipient("%s@example.org" % username))
    )


review_counter = 0


class Review(object):
    def __init__(self, workcopy, as_user, work_branch_name=None, *, fork_point="HEAD"):
        global review_counter
        review_counter += 1
        review_index = review_counter
        self.workcopy = workcopy
        self.repository_url = instance.repository_url(
            as_user, repository=workcopy.clone_of
        )
        if work_branch_name is None:
            work_branch_name = f"{test.name}/{review_index}"
        self.base_branch_name = "base/" + work_branch_name
        self.work_branch_name = work_branch_name
        self.review_branch_name = "r/" + work_branch_name
        self.summary = work_branch_name
        self.as_user = as_user
        self.sha1s = []
        self.reference_commits = set()
        self.pushed_commits = set()
        self.files = {}
        self.json = None
        self.id = None
        self.filters = []
        self.users = {as_user}
        self.__notified_users = {as_user}
        self.__commit_ids = {}
        self.__base_sha1 = self.workcopy.run(["rev-parse", "HEAD"]).strip()
        self.expected_partitions = []
        self.target_branch = None

        self.workcopy.run(["checkout", "-b", self.base_branch_name, fork_point])
        self.current_branch = self.base_branch_name

    class File(object):
        def __init__(self, filename):
            self.filename = f"{test.name}/{filename}"
            self.content = None
            self.__file_id = None

        @property
        def id(self):
            if self.__file_id is None:
                self.__file_id = frontend.json(
                    "files",
                    params={"path": self.filename},
                    expect={"id": int, "path": self.filename},
                )["id"]
            return self.__file_id

        def write(self, path):
            filename = os.path.join(path, self.filename)
            if self.content is None:
                if not os.path.isfile(filename):
                    return False
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
            return True

    def addFile(self, **files):
        for key, filename in files.items():
            self.files[key] = Review.File(filename)

    def getFilename(self, key):
        return self.files[key].filename

    def getFileId(self, key):
        return self.files[key].id

    def getCommitId(self, sha1):
        if sha1 not in self.__commit_ids:
            self.__commit_ids[sha1] = frontend.json(
                "commits",
                params={
                    "repository": self.workcopy.clone_of,
                    "sha1": sha1,
                    "fields": "id",
                },
            )["id"]
        return self.__commit_ids[sha1]

    @property
    def last_reference_commit(self):
        return max({-1} | self.reference_commits)

    @property
    def last_pushed_commit(self):
        return max({0} | self.pushed_commits)

    def ensure_branch(self, branch):
        if branch == self.current_branch:
            return
        output = self.workcopy.run(["for-each-ref", "refs/heads/" + branch])
        if not output.strip():
            self.workcopy.run(["branch", branch])
        self.workcopy.run(["checkout", branch])
        self.current_branch = branch

    def commit(self, message, **files):
        if files.pop("reference", False):
            self.reference_commits.add(len(self.sha1s))
            wanted_branch = self.base_branch_name
        else:
            wanted_branch = self.work_branch_name
        self.ensure_branch(wanted_branch)
        for key, content in files.items():
            self.files[key].content = content
        for file_ in self.files.values():
            if file_.write(self.workcopy.path):
                self.workcopy.run(["add", file_.filename])
        self.workcopy.run(["commit", "-m", message])
        self.sha1s.append(self.workcopy.run(["rev-parse", "HEAD"]).strip())
        return self.sha1s[-1]

    def addFilter(self, username, filter_type, path=None):
        if path is None:
            path = f"{test.name}/"
        assert filter_type in ("reviewer", "watcher", "ignored")
        self.users.add(username)
        self.filters.append({"username": username, "type": filter_type, "path": path})

    def flushFilters(self, expect_mail=True):
        with frontend.signin(self.as_user):
            frontend.json(
                "reviews/%d/reviewfilters" % self.id,
                post={
                    "reviewfilters": [
                        {
                            "subject": filter["username"],
                            "type": filter["type"],
                            "path": filter["path"],
                        }
                        for filter in self.filters
                    ]
                },
            )

        self.filters = []

        if expect_mail:
            pass

    def checkIncludedCommits(self, expected_sha1s, mail):
        actual_sha1s = []

        for line in mail.lines:
            match = re.match("^Commit: ([0-9a-f]{40})$", line)
            if match:
                sha1, = match.groups()
                actual_sha1s.append(sha1)

        try:
            testing.expect.equal(
                list(reversed(expected_sha1s)),
                actual_sha1s,
                message="%r to <%s>" % (mail.subject, mail.recipient),
            )
        except Exception:
            testing.logger.debug(str(mail))
            raise

    def submit(self):
        assert self.current_branch == self.work_branch_name

        self.workcopy.run(["push", self.repository_url, self.base_branch_name])
        self.ensure_branch(self.work_branch_name)

        self.workcopy.run(["push", self.repository_url, "HEAD"])
        self.pushed_commits.update(
            range(self.last_reference_commit + 1, len(self.sha1s))
        )

        initial_sha1s = self.sha1s[self.last_reference_commit + 1 :]
        data = {
            "repository": self.workcopy.clone_of,
            "branch": self.review_branch_name,
            "commits": initial_sha1s,
            "summary": self.summary,
        }

        if self.target_branch:
            data["integration"] = {"target_branch": target_branch["id"]}

        with frontend.signin(self.as_user):
            self.json = frontend.json(
                "reviews", params={"include": "commits"}, post=data
            )
            self.id = self.json["id"]

            for commit in self.json["linked"]["commits"]:
                self.__commit_ids[commit["sha1"]] = commit["id"]

        commit_ids = list(reversed([self.__commit_ids[sha1] for sha1 in initial_sha1s]))

        self.expected_partitions.append({"commits": commit_ids, "rebase": None})

        instance.synchronize_service("reviewupdater")

        if self.filters:
            self.flushFilters(expect_mail=False)

        # Not published yet, so no emails are expected.
        mailbox.check_empty()

        with frontend.signin(self.as_user):
            frontend.json("reviews/%d" % self.id, put={"state": "open"})

        instance.synchronize_service("reviewevents")

        initial_sha1s = self.sha1s[self.last_reference_commit + 1 :]

        for username in self.users:
            mail = mailbox.pop(
                accept=[
                    testing.mailbox.ToRecipient(username + "@example.org"),
                    testing.mailbox.WithSubject("New Review: " + self.summary),
                ]
            )
            self.checkIncludedCommits(initial_sha1s, mail)
            self.__notified_users.add(username)

        mailbox.check_empty()

    def push_reference_branch(self):
        self.workcopy.run(["push", self.repository_url, self.base_branch_name])

    def push(self, *, history_rewrite=None, move_rebase=None):
        assert self.id is not None, "call review.submit() first!"

        self.push_reference_branch()
        self.ensure_branch(self.work_branch_name)

        current_sha1s = self.sha1s[
            self.last_reference_commit + 1 : self.last_pushed_commit + 1
        ]
        pushed_sha1s = self.sha1s[self.last_pushed_commit + 1 :]

        self.pushed_commits.update(range(self.last_pushed_commit + 1, len(self.sha1s)))

        argv = ["push"]

        if history_rewrite or move_rebase:
            argv.append("--force")

        argv.extend([self.repository_url, "HEAD:" + self.review_branch_name])

        self.workcopy.run(argv)

        for username in self.users:
            if username not in self.__notified_users:
                mail = mailbox.pop(
                    accept=[
                        testing.mailbox.ToRecipient(username + "@example.org"),
                        testing.mailbox.WithSubject(
                            r"New\(ish\) Review: " + self.summary
                        ),
                    ]
                )
                self.checkIncludedCommits(current_sha1s, mail)
                self.__notified_users.add(username)

            mail = mailbox.pop(
                accept=[
                    testing.mailbox.ToRecipient(username + "@example.org"),
                    testing.mailbox.WithSubject("Updated Review: " + self.summary),
                ]
            )
            if history_rewrite:
                pass
            elif move_rebase:
                pass
            else:
                self.checkIncludedCommits(pushed_sha1s, mail)

        if history_rewrite or move_rebase:
            if history_rewrite is not None:
                rebase_id = history_rewrite
            else:
                rebase_id = move_rebase
            self.expected_partitions.insert(0, {"commits": [], "rebase": rebase_id})
        else:
            self.expected_partitions[0]["commits"][:0] = list(
                reversed([self.getCommitId(sha1) for sha1 in pushed_sha1s])
            )

    def reset(self, sha1=None):
        self.ensure_branch(self.work_branch_name)
        if sha1 is None:
            assert self.reference_commits
            sha1 = self.sha1s[self.last_reference_commit]
        else:
            assert sha1 != self.sha1s[-1]
        assert sha1 in self.sha1s
        self.workcopy.run(["reset", "--hard", sha1])

    def checkMails(self, subject, callback, *, recipients=None):
        if recipients is None:
            recipients = self.users
        for username in recipients:
            callback(
                mailbox.pop(
                    accept=[
                        testing.mailbox.ToRecipient(instance.user(username).email),
                        testing.mailbox.WithSubject(f"{subject}: {self.summary}"),
                    ]
                )
            )

    def expectMails(self, subject, *, recipients=None):
        self.checkMails(subject, lambda mail: True, recipients=recipients)

    def getBranch(self):
        return frontend.json(f"branches/{self.json['branch']}")

    def getBranchCommits(self):
        return frontend.json(
            f"branches/{self.json['branch']}/commits", extract="commits"
        )


def override_system_settings(settings):
    def update(settings):
        updates = sorted(settings.items())
        keys = [key for key, _ in updates]

        old_values = json.loads(instance.criticctl(["settings", "get"] + keys))
        stdin_data = "\n".join(json.dumps(value) for _, value in updates) + "\n"

        instance.criticctl(["settings", "set"] + keys, stdin_data=stdin_data)
        instance.restart()

        return old_values

    testing.after_test(update, update(settings))


def build_json_map(result):
    data = {}

    def process(resource_class, values):
        resource_data = data.setdefault(resource_class, {})
        for value in values:
            value_id = value["id"] if "id" in value else value["file"]
            resource_data[value_id] = value

    for resource_class, values in result.items():
        if resource_class == "linked":
            for linked_resource_class, linked_values in values.items():
                process(linked_resource_class, linked_values)
        else:
            process(resource_class, values)

    class Map:
        def __init__(self, data):
            self.data = data

        def __getattr__(self, name):
            try:
                return self.data[name]
            except KeyError:
                raise AttributeError(name) from None

    return Map(data)


NONSENSE = """
Lorem ipsum dolor sit amet, consectetur adipiscing
elit. Donec ut enim sit amet purus ultricies
lobortis. Pellentesque nisi arcu, convallis sed purus sed,
semper ultrices velit. Ut egestas lorem tortor, vitae
lacinia lorem consectetur nec. Integer tempor ornare ipsum
at viverra. Curabitur nec orci mollis, lacinia sapien eget,
ultricies ipsum. Curabitur a libero tortor. Curabitur
volutpat lacinia erat, ac suscipit enim dignissim nec.
"""


def nonsense(*versions):
    import textwrap

    return (
        "\n\n".join(
            textwrap.indent(NONSENSE, f"[{version}] ").strip() for version in versions
        )
        + "\n"
    )


def fetch_changeset(params, repository="critic"):
    params.setdefault("repository", repository)

    result = frontend.json("changesets", params=params, expected_http_status=[200, 202])

    if "error" in result:
        instance.synchronize_service("changeset")

        result = frontend.json(
            "changesets", params=params, expect={"id": int, "*": "*"}
        )

    return result


def batch_json(review_id, author, batch_type, **fields):
    expected = {
        "id": int,
        "is_empty": not fields,
        "review": review_id,
        "author": instance.userid(author),
        "comment": None,
        "timestamp": float,
        "created_comments": [],
        "written_replies": [],
        "resolved_issues": [],
        "reopened_issues": [],
        "morphed_comments": [],
        "reviewed_changes": [],
        "unreviewed_changes": [],
    }

    if batch_type == "draft":
        expected.update({"id": None, "timestamp": None})

    expected.update(fields)

    return expected


def comment_draft_changes_json(author, **kwargs):
    result = {
        "author": instance.userid(author),
        "is_draft": False,
        "reply": None,
        "new_type": None,
        "new_state": None,
        "new_location": None,
    }
    result.update(kwargs)
    return result
