# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import time

import base

def countDraftItems(db, user, review):
    cursor = db.readonly_cursor()

    cursor.execute("""SELECT reviewfilechanges.to_state, SUM(deleted) + SUM(inserted)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE reviewfiles.review=%s
                         AND reviewfilechanges.uid=%s
                         AND reviewfilechanges.state='draft'
                    GROUP BY reviewfilechanges.to_state""",
                   (review.id, user.id))

    reviewed = unreviewed = 0

    for to_state, lines in cursor:
        if to_state == "reviewed": reviewed = lines
        else: unreviewed = lines

    cursor.execute("""SELECT reviewfilechanges.to_state, COUNT(*)
                        FROM reviewfiles
                        JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id)
                       WHERE reviewfiles.review=%s
                         AND reviewfiles.deleted=0
                         AND reviewfiles.inserted=0
                         AND reviewfilechanges.uid=%s
                         AND reviewfilechanges.state='draft'
                    GROUP BY reviewfilechanges.to_state""",
                   (review.id, user.id))

    reviewedBinary = unreviewedBinary = 0

    for to_state, lines in cursor:
        if to_state == "reviewed": reviewedBinary = lines
        else: unreviewedBinary = lines

    cursor.execute("SELECT count(*) FROM commentchains, comments WHERE commentchains.review=%s AND comments.chain=commentchains.id AND comments.uid=%s AND comments.state='draft'", [review.id, user.id])
    comments = cursor.fetchone()[0]

    cursor.execute("""SELECT DISTINCT commentchains.id
                        FROM commentchains
                        JOIN commentchainchanges ON (commentchainchanges.chain=commentchains.id)
                       WHERE commentchains.review=%s
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND ((commentchains.state=commentchainchanges.from_state
                           AND commentchainchanges.from_state IN ('addressed', 'closed')
                           AND commentchainchanges.to_state='open')
                          OR (commentchainchanges.from_addressed_by IS NOT NULL
                           AND commentchainchanges.to_addressed_by IS NOT NULL))""",
                   [review.id, user.id])
    reopened = len(cursor.fetchall())

    cursor.execute("""SELECT count(*) FROM commentchains, commentchainchanges
                       WHERE commentchains.review=%s
                         AND commentchains.state='open'
                         AND commentchainchanges.chain=commentchains.id
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND commentchainchanges.from_state='open'
                         AND commentchainchanges.to_state='closed'""",
                   [review.id, user.id])
    closed = cursor.fetchone()[0]

    cursor.execute("""SELECT count(*) FROM commentchains, commentchainchanges
                       WHERE commentchains.review=%s
                         AND commentchainchanges.chain=commentchains.id
                         AND commentchainchanges.uid=%s
                         AND commentchainchanges.state='draft'
                         AND commentchainchanges.from_type=commentchains.type
                         AND commentchainchanges.to_type!=commentchains.type""",
                   [review.id, user.id])
    morphed = cursor.fetchone()[0]

    return { "reviewedNormal": reviewed,
             "unreviewedNormal": unreviewed,
             "reviewedBinary": reviewedBinary,
             "unreviewedBinary": unreviewedBinary,
             "writtenComments": comments,
             "reopenedIssues": reopened,
             "resolvedIssues": closed,
             "morphedChains": morphed }

class NoSuchReview(base.Error):
    def __init__(self, review_id):
        super(NoSuchReview, self).__init__("No such review: r/%d" % review_id)
        self.id = review_id

class ReviewState(object):
    def __init__(self, review, accepted, pending, reviewed, issues):
        self.review = review
        self.accepted = accepted
        self.pending = pending
        self.reviewed = reviewed
        self.issues = issues

    def getPercentReviewed(self):
        if self.pending + self.reviewed:
            return 100.0 * self.reviewed / (self.pending + self.reviewed)
        else:
            return 50.0

    def getProgress(self):
        if self.pending + self.reviewed == 0:
            return "?? %"
        percent = self.getPercentReviewed()
        if int(percent) > 0 and (percent < 99.0 or percent == 100.0):
            return "%d %%" % int(percent)
        elif percent > 0:
            precision = 1
            while precision < 10:
                progress = ("%%.%df" % precision) % percent
                if progress[-1] != '0': break
                precision += 1
            return progress + " %"
        else:
            return "No progress"

    def getIssues(self):
        if self.issues: return "%d issue%s" % (self.issues, "s" if self.issues > 1 else "")
        else: return ""

    def __str__(self):
        if self.review.state == 'dropped': return "Dropped..."
        elif self.review.state == 'closed': return "Finished!"
        elif self.accepted: return "Accepted!"
        else:
            progress = self.getProgress()
            issues = self.getIssues()
            if issues: return "%s and %s" % (progress, issues)
            else: return progress

class ReviewRebase(object):
    def __init__(self, review, old_head, new_head, old_upstream, new_upstream, user,
                 equivalent_merge, replayed_rebase):
        self.review = review
        self.old_head = old_head
        self.new_head = new_head
        self.old_upstream = old_upstream
        self.new_upstream = new_upstream
        self.user = user
        self.equivalent_merge = equivalent_merge
        self.replayed_rebase = replayed_rebase

class ReviewRebases(list):
    def __init__(self, db, review):
        import gitutils
        from dbutils import User

        self.__old_head_map = {}
        self.__new_head_map = {}

        cursor = db.cursor()
        cursor.execute("""SELECT old_head, new_head, old_upstream, new_upstream, uid,
                                 equivalent_merge, replayed_rebase
                            FROM reviewrebases
                           WHERE review=%s
                             AND new_head IS NOT NULL""",
                       (review.id,))

        for (old_head_id, new_head_id, old_upstream_id, new_upstream_id, user_id,
             equivalent_merge_id, replayed_rebase_id) in cursor:
            old_head = gitutils.Commit.fromId(db, review.repository, old_head_id)
            new_head = gitutils.Commit.fromId(db, review.repository, new_head_id)

            if old_upstream_id is not None and new_upstream_id is not None:
                old_upstream = gitutils.Commit.fromId(db, review.repository, old_upstream_id)
                new_upstream = gitutils.Commit.fromId(db, review.repository, new_upstream_id)
            else:
                old_upstream = new_upstream = None

            if equivalent_merge_id:
                equivalent_merge = gitutils.Commit.fromId(db, review.repository, equivalent_merge_id)
            else:
                equivalent_merge = None

            if replayed_rebase_id:
                replayed_rebase = gitutils.Commit.fromId(db, review.repository, replayed_rebase_id)
            else:
                replayed_rebase = None

            user = User.fromId(db, user_id)
            rebase = ReviewRebase(review, old_head, new_head, old_upstream, new_upstream, user,
                                  equivalent_merge, replayed_rebase)

            self.append(rebase)
            self.__old_head_map[old_head] = rebase
            self.__new_head_map[new_head] = rebase

            if equivalent_merge:
                self.__old_head_map[equivalent_merge] = rebase

        if review.performed_rebase:
            self.__old_head_map[review.performed_rebase.old_head] = review.performed_rebase
            self.__new_head_map[review.performed_rebase.new_head] = review.performed_rebase

    def fromOldHead(self, commit):
        return self.__old_head_map.get(commit)

    def fromNewHead(self, commit):
        return self.__new_head_map.get(commit)

class ReviewTrackedBranch(object):
    def __init__(self, review, trackedbranch_id, remote, name, disabled):
        self.id = trackedbranch_id
        self.review = review
        self.remote = remote
        self.name = name
        self.disabled = disabled

class Review(object):
    def __init__(self, review_id, owners, review_type, branch, state, serial, summary, description, applyfilters, applyparentfilters):
        self.id = review_id
        self.owners = owners
        self.type = review_type
        self.repository = branch.repository
        self.branch = branch
        self.state = state
        self.serial = serial
        self.summary = summary
        self.description = description
        self.reviewers = []
        self.watchers = {}
        self.commentchains = None
        self.applyfilters = applyfilters
        self.applyparentfilters = applyparentfilters
        self.filters = None
        self.relevant_files = None
        self.draft_status = None
        self.performed_rebase = None

    @staticmethod
    def isAccepted(db, review_id):
        cursor = db.readonly_cursor()

        cursor.execute("SELECT 1 FROM reviewfiles WHERE review=%s AND state='pending' LIMIT 1", (review_id,))
        if cursor.fetchone(): return False

        cursor.execute("SELECT 1 FROM commentchains WHERE review=%s AND type='issue' AND state='open' LIMIT 1", (review_id,))
        if cursor.fetchone(): return False

        return True

    def accepted(self, db):
        if self.state != 'open': return False
        else: return Review.isAccepted(db, self.id)

    def getReviewState(self, db):
        cursor = db.readonly_cursor()

        cursor.execute("""SELECT state, SUM(deleted) + SUM(inserted)
                            FROM reviewfiles
                           WHERE reviewfiles.review=%s
                        GROUP BY state""",
                       (self.id,))

        pending = 0
        reviewed = 0

        for state, count in cursor.fetchall():
            if state == "pending": pending = count
            else: reviewed = count

        cursor.execute("""SELECT count(id)
                            FROM commentchains
                           WHERE review=%s
                             AND type='issue'
                             AND state='open'""",
                       (self.id,))

        issues = cursor.fetchone()[0]

        return ReviewState(self, self.accepted(db), pending, reviewed, issues)

    def setPerformedRebase(self, old_head, new_head, old_upstream, new_upstream, user,
                           equivalent_merge, replayed_rebase):
        self.performed_rebase = ReviewRebase(self, old_head, new_head, old_upstream, new_upstream, user,
                                             equivalent_merge, replayed_rebase)

    def getReviewRebases(self, db):
        return ReviewRebases(db, self)

    def getTrackedBranch(self, db):
        cursor = db.readonly_cursor()
        cursor.execute("""SELECT trackedbranches.id, remote, remote_name, disabled
                            FROM trackedbranches
                            JOIN branches ON (trackedbranches.repository=branches.repository
                                          AND trackedbranches.local_name=branches.name)
                            JOIN reviews ON (branches.id=reviews.branch)
                           WHERE reviews.id=%s""",
                       (self.id,))

        for trackedbranch_id, remote, name, disabled in cursor:
            return ReviewTrackedBranch(self, trackedbranch_id, remote, name, disabled)

    def getCommitSet(self, db):
        import gitutils
        import log.commitset

        cursor = db.readonly_cursor()
        cursor.execute("""SELECT DISTINCT commits.id, commits.sha1
                            FROM commits
                            JOIN changesets ON (changesets.child=commits.id)
                            JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
                           WHERE reviewchangesets.review=%s""",
                       (self.id,))

        commits = []

        for commit_id, commit_sha1 in cursor:
            commits.append(gitutils.Commit.fromSHA1(db, self.repository, commit_sha1, commit_id))

        return log.commitset.CommitSet(commits)

    def containsCommit(self, db, commit, include_head_and_tails=False, include_actual_log=False):
        import gitutils

        commit_id = None
        commit_sha1 = None

        if isinstance(commit, gitutils.Commit):
            commit_id = commit.id
            commit_sha1 = commit.sha1
        elif isinstance(commit, str):
            commit_sha1 = self.repository.revparse(commit)
            commit = None
        elif isinstance(commit, int):
            commit_id = commit
            commit = None
        else:
            raise TypeError

        cursor = db.readonly_cursor()

        if commit_id is not None:
            cursor.execute("""SELECT 1
                                FROM reviewchangesets
                                JOIN changesets ON (id=changeset)
                               WHERE reviewchangesets.review=%s
                                 AND changesets.child=%s
                                 AND changesets.type!='conflicts'""",
                           (self.id, commit_id))
        else:
            cursor.execute("""SELECT 1
                                FROM reviewchangesets
                                JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                                JOIN commits ON (commits.id=changesets.child)
                               WHERE reviewchangesets.review=%s
                                 AND changesets.type!='conflicts'
                                 AND commits.sha1=%s""",
                           (self.id, commit_sha1))

        if cursor.fetchone() is not None:
            return True

        if include_head_and_tails:
            head_and_tails = set([self.branch.getHead(db)])

            commitset = self.getCommitSet(db)

            if commitset:
                head_and_tails |= commitset.getTails()

            if commit_sha1 is None:
                if commit is None:
                    commit = gitutils.Commit.fromId(db, self.repository, commit_id)
                commit_sha1 = commit.sha1

            if commit_sha1 in head_and_tails:
                return True

        if include_actual_log:
            if commit_id is not None:
                cursor.execute("""SELECT 1
                                    FROM reachable
                                    JOIN branches ON (branches.id=reachable.branch)
                                    JOIN reviews ON (reviews.branch=branches.id)
                                   WHERE reachable.commit=%s
                                     AND reviews.id=%s""",
                               (commit_id, self.id))
            else:
                cursor.execute("""SELECT 1
                                    FROM commits
                                    JOIN reachable ON (reachable.commit=commits.id)
                                    JOIN branches ON (branches.id=reachable.branch)
                                    JOIN reviews ON (reviews.branch=branches.id)
                                   WHERE commits.sha1=%s
                                     AND reviews.id=%s""",
                               (commit_sha1, self.id))

            if cursor.fetchone() is not None:
                return True

        return False

    def getJS(self):
        return "var review = critic.review = { id: %d, branch: { id: %d, name: %r }, owners: [ %s ], serial: %d };" % (self.id, self.branch.id, self.branch.name, ", ".join(owner.getJSConstructor() for owner in self.owners), self.serial)

    def getETag(self, db, user=None):
        import configuration

        cursor = db.readonly_cursor()
        etag = ""

        if configuration.debug.IS_DEVELOPMENT:
            cursor.execute("SELECT installed_at FROM systemidentities WHERE name=%s", (configuration.base.SYSTEM_IDENTITY,))
            installed_at = cursor.fetchone()[0]
            etag += "install%s." % time.mktime(installed_at.timetuple())

        if user and not user.isAnonymous():
            etag += "user%d." % user.id

        etag += "review%d.serial%d" % (self.id, self.serial)

        if user:
            items = self.getDraftStatus(db, user)
            if any(items.values()):
                etag += ".draft%d" % hash(tuple(sorted(items.items())))

            cursor.execute("SELECT id FROM reviewrebases WHERE review=%s AND uid=%s AND new_head IS NULL", (self.id, user.id))
            row = cursor.fetchone()
            if row:
                etag += ".rebase%d" % row[0]

        return '"%s"' % etag

    def getURL(self, db, user=None, indent=0, separator="\n"):
        import dbutils

        indent = " " * indent

        if user:
            url_prefixes = user.getCriticURLs(db)
        else:
            url_prefixes = [dbutils.getURLPrefix(db)]

        return separator.join(["%s%s/r/%d" % (indent, url_prefix, self.id) for url_prefix in url_prefixes])

    def getRecipients(self, db):
        from dbutils import User

        cursor = db.readonly_cursor()
        cursor.execute("SELECT uid, include FROM reviewrecipientfilters WHERE review=%s", (self.id,))

        default_include = True
        included = set(owner.id for owner in self.owners)
        excluded = set()

        for uid, include in cursor:
            if uid is None:
                default_include = include
            elif include:
                included.add(uid)
            elif uid not in self.owners:
                excluded.add(uid)

        cursor.execute("SELECT uid FROM reviewusers WHERE review=%s", (self.id,))

        recipients = []
        for (user_id,) in cursor:
            if user_id in excluded:
                continue
            elif user_id not in included and not default_include:
                continue

            user = User.fromId(db, user_id)
            if user.status != "retired":
                recipients.append(user)

        return recipients

    def getDraftStatus(self, db, user):
        if self.draft_status is None:
            self.draft_status = countDraftItems(db, user, self)
        return self.draft_status

    def incrementSerial(self, db):
        self.serial += 1
        db.cursor().execute("UPDATE reviews SET serial=%s WHERE id=%s", [self.serial, self.id])

    def scheduleBranchArchival(self, db, delay=None):
        import dbutils

        # First, cancel current scheduled archival, if there is one.
        self.cancelScheduledBranchArchival(db)

        # If review is not closed or dropped, don't schedule a branch archival.
        # Also don't schedule one if the branch has already been archived.
        if self.state not in ("closed", "dropped") or self.branch.archived:
            return

        if delay is None:
            # Configuration policy:
            #
            # Any owner of a review can, by having changed the relevant
            # preference setting, increase the time before a review branch is
            # archived, or disable archival entirely, but they can't make it
            # happen sooner than the system or repository default, or what any
            # other owner has requested.

            # Find configured value for each owner, and also the per-repository
            # (or per-system) default, in case each owner has changed the
            # setting.
            preference_item = "review.branchArchiveDelay." + self.state
            repository_default = dbutils.User.fetchPreference(
                db, preference_item, repository=self.repository)
            delays = set([repository_default])
            for owner in self.owners:
                delays.add(owner.getPreference(db, preference_item,
                                               repository=self.repository))

            # If configured to zero (by any owner,) don't schedule a branch
            # archival.
            if min(delays) <= 0:
                return

            # Otherwise, use maximum configured value for any owner.
            delay = max(delays)

        cursor = db.cursor()
        cursor.execute("""INSERT INTO scheduledreviewbrancharchivals (review, deadline)
                               VALUES (%s, NOW() + INTERVAL %s)""",
                       (self.id, "%d DAYS" % delay))

        return delay

    def cancelScheduledBranchArchival(self, db):
        cursor = db.cursor()
        cursor.execute("""DELETE FROM scheduledreviewbrancharchivals
                                WHERE review=%s""",
                       (self.id,))

    def close(self, db, user):
        self.serial += 1
        self.state = "closed"
        db.cursor().execute("UPDATE reviews SET state='closed', serial=%s, closed_by=%s WHERE id=%s", (self.serial, user.id, self.id))
        self.scheduleBranchArchival(db)

    def drop(self, db, user):
        self.serial += 1
        self.state = "dropped"
        db.cursor().execute("UPDATE reviews SET state='dropped', serial=%s, closed_by=%s WHERE id=%s", (self.serial, user.id, self.id))
        self.scheduleBranchArchival(db)

    def reopen(self, db, user):
        self.serial += 1
        if self.branch.archived:
            self.branch.resurrect(db)
        db.cursor().execute("UPDATE reviews SET state='open', serial=%s, closed_by=NULL WHERE id=%s", (self.serial, self.id))
        self.cancelScheduledBranchArchival(db)

    def disableTracking(self, db):
        db.cursor().execute("UPDATE trackedbranches SET disabled=TRUE WHERE repository=%s AND local_name=%s", (self.repository.id, self.branch.name))

    def setSummary(self, db, summary):
        self.serial += 1
        self.summary = summary
        db.cursor().execute("UPDATE reviews SET summary=%s, serial=%s WHERE id=%s", [self.summary, self.serial, self.id])

    def setDescription(self, db, description):
        self.serial += 1
        self.description = description
        db.cursor().execute("UPDATE reviews SET description=%s, serial=%s WHERE id=%s", [self.description, self.serial, self.id])

    def addOwner(self, db, owner):
        if not owner in self.owners:
            self.serial += 1
            self.owners.append(owner)

            cursor = db.cursor()
            cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (self.id, owner.id))

            if cursor.fetchone():
                cursor.execute("UPDATE reviewusers SET owner=TRUE WHERE review=%s AND uid=%s", (self.id, owner.id))
            else:
                cursor.execute("INSERT INTO reviewusers (review, uid, owner) VALUES (%s, %s, TRUE)", (self.id, owner.id))

            cursor.execute("SELECT id FROM trackedbranches WHERE repository=%s AND local_name=%s", (self.repository.id, self.branch.name))

            row = cursor.fetchone()
            if row:
                trackedbranch_id = row[0]
                cursor.execute("INSERT INTO trackedbranchusers (branch, uid) VALUES (%s, %s)", (trackedbranch_id, owner.id))

    def removeOwner(self, db, owner):
        if owner in self.owners:
            self.serial += 1
            self.owners.remove(owner)

            cursor = db.cursor()
            cursor.execute("UPDATE reviewusers SET owner=FALSE WHERE review=%s AND uid=%s", (self.id, owner.id))
            cursor.execute("SELECT id FROM trackedbranches WHERE repository=%s AND local_name=%s", (self.repository.id, self.branch.name))

            row = cursor.fetchone()
            if row:
                trackedbranch_id = row[0]
                cursor.execute("DELETE FROM trackedbranchusers WHERE branch=%s AND uid=%s", (trackedbranch_id, owner.id))

    def getReviewFilters(self, db):
        cursor = db.readonly_cursor()
        cursor.execute("SELECT uid, path, type, NULL FROM reviewfilters WHERE review=%s", (self.id,))
        return cursor.fetchall() or None

    def getFilteredTails(self, db):
        import log.commitset
        commitset = log.commitset.CommitSet(self.branch.getCommits(db))
        return commitset.getFilteredTails(self.branch.repository)

    def getRelevantFiles(self, db, user):
        if not self.filters:
            from reviewing.filters import Filters

            self.filters = Filters()
            self.filters.setFiles(db, review=self)
            self.filters.load(db, review=self)
            self.relevant_files = self.filters.getRelevantFiles()

            cursor = db.readonly_cursor()
            cursor.execute("SELECT assignee, file FROM fullreviewuserfiles WHERE review=%s", (self.id,))
            for user_id, file_id in cursor:
                self.relevant_files.setdefault(user_id, set()).add(file_id)

        return self.relevant_files.get(user.id, set())

    def getUserAssociation(self, db, user):
        cursor = db.readonly_cursor()

        association = []

        if user in self.owners:
            association.append("owner")

        cursor.execute("""SELECT 1
                            FROM reviewchangesets
                            JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                            JOIN commits ON (commits.id=changesets.child)
                            JOIN gitusers ON (gitusers.id=commits.author_gituser)
                            JOIN usergitemails USING (email)
                           WHERE reviewchangesets.review=%s
                             AND usergitemails.uid=%s""",
                       (self.id, user.id))
        if cursor.fetchone():
            association.append("author")

        cursor.execute("SELECT COUNT(*) FROM fullreviewuserfiles WHERE review=%s AND assignee=%s", (self.id, user.id))
        if cursor.fetchone()[0] != 0:
            association.append("reviewer")
        elif user not in self.owners:
            cursor.execute("SELECT 1 FROM reviewusers WHERE review=%s AND uid=%s", (self.id, user.id))
            if cursor.fetchone():
                association.append("watcher")

        if not association:
            association.append("none")

        return ", ".join(association)

    @staticmethod
    def fromId(db, review_id, branch=None, profiler=None):
        from dbutils import User

        cursor = db.readonly_cursor()
        cursor.execute("SELECT type, branch, state, serial, summary, description, applyfilters, applyparentfilters FROM reviews WHERE id=%s", [review_id])
        row = cursor.fetchone()
        if not row: raise NoSuchReview(review_id)

        type, branch_id, state, serial, summary, description, applyfilters, applyparentfilters = row

        if profiler: profiler.check("Review.fromId: basic")

        if branch is None:
            from dbutils import Branch
            branch = Branch.fromId(db, branch_id, load_review=False, profiler=profiler)

        cursor.execute("SELECT uid FROM reviewusers WHERE review=%s AND owner", (review_id,))

        owners = User.fromIds(db, [user_id for (user_id,) in cursor])

        if profiler: profiler.check("Review.fromId: owners")

        review = Review(review_id, owners, type, branch, state, serial, summary, description, applyfilters, applyparentfilters)
        branch.review = review

        # Reviewers: all users that have at least one review file assigned to them.
        cursor.execute("""SELECT DISTINCT uid, assignee IS NOT NULL, type
                            FROM reviewusers
                 LEFT OUTER JOIN fullreviewuserfiles ON (fullreviewuserfiles.review=reviewusers.review AND assignee=uid)
                           WHERE reviewusers.review=%s""",
                       (review_id,))

        reviewers = []
        watchers = []
        watcher_types = {}

        for user_id, is_reviewer, user_type in cursor.fetchall():
            if is_reviewer:
                reviewers.append(user_id)
            elif user_id not in review.owners:
                watchers.append(user_id)
                watcher_types[user_id] = user_type

        review.reviewers = User.fromIds(db, reviewers)

        for watcher in User.fromIds(db, watchers):
            review.watchers[watcher] = watcher_types[watcher]

        if profiler: profiler.check("Review.fromId: users")

        return review

    @staticmethod
    def fromBranch(db, branch):
        if branch:
            cursor = db.readonly_cursor()
            cursor.execute("SELECT id FROM reviews WHERE branch=%s", [branch.id])
            row = cursor.fetchone()
            if not row: return None
            else: return Review.fromId(db, row[0], branch)
        else:
            return None

    @staticmethod
    def fromName(db, repository, name):
        from dbutils import Branch
        return Review.fromBranch(db, Branch.fromName(db, repository, name))

    @staticmethod
    def fromArgument(db, argument):
        try:
            return Review.fromId(db, int(argument))
        except:
            from dbutils import Branch
            branch = Branch.fromName(db, str(argument))
            if not branch: return None
            return Review.fromBranch(db, branch)

    @staticmethod
    def fromAPI(api_review):
        return Review.fromId(api_review.critic.database, api_review.id)
