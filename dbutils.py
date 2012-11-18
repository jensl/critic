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

import base
import gitutils
from htmlutils import jsify
import configuration
#import review.utils as review_utils
from log.commitset import CommitSet
import dbaccess

from dbaccess import IntegrityError

import os
import os.path
import time

class Session():
    def __init__(self):
        self.__atexit = []
        self.storage = { "Repository": {}, "User": {}, "Commit": {}, "CommitUserTime": {} }
        self.profiling = {}

    def atexit(self, fn):
        self.__atexit.append(fn)

    def close(self):
        for fn in self.__atexit:
            try: fn(self)
            except: pass

    def disableProfiling(self):
        self.profiling = None

    def recordProfiling(self, item, duration, rows=None, repetitions=1):
        if self.profiling is not None:
            count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows = self.profiling.get(item, (0, 0.0, 0.0, None, None))

            count += repetitions
            accumulated_ms += 1000 * duration
            maximum_ms = max(maximum_ms, 1000 * duration)

            if rows is not None:
                if accumulated_rows is None: accumulated_rows = 0
                if maximum_rows is None: maximum_rows = 0
                accumulated_rows += rows
                maximum_rows = max(maximum_rows, rows)

            self.profiling[item] = count, accumulated_ms, maximum_ms, accumulated_rows, maximum_rows

class Database(Session):
    class Cursor():
        def __init__(self, db, cursor, profiling):
            self.__db = db
            self.__cursor = cursor
            self.__profiling = self.__db.profiling is not None
            self.__rows = None

        def __iter__(self):
            if not self.__profiling:
                return iter(self.__cursor)
            else:
                return iter(self.__rows)

        def __getitem__(self, index):
            if not self.__profiling:
                return self.__cursor[index]
            else:
                return self.__rows[index]

        def fetchone(self):
            if not self.__profiling:
                return self.__cursor.fetchone()
            elif self.__rows:
                row = self.__rows[0]
                self.__rows = self.__rows[1:]
                return row
            else:
                return None

        def fetchall(self):
            if not self.__profiling:
                return self.__cursor.fetchall()
            else:
                return self.__rows

        def execute(self, query, params=None):
            if not self.__profiling:
                self.__cursor.execute(query, params)
            else:
                before = time.time()
                self.__cursor.execute(query, params)
                try:
                    self.__rows = self.__cursor.fetchall()
                except dbaccess.ProgrammingError:
                    self.__rows = None
                after = time.time()
                self.__db.recordProfiling(query, after - before, rows=len(self.__rows) if self.__rows else 0)

        def executemany(self, query, params):
            if self.__profiling is None:
                self.__cursor.executemany(query, params)
            else:
                before = time.time()
                params = list(params)
                self.__cursor.executemany(query, params)
                after = time.time()
                self.__db.recordProfiling(query, after - before, repetitions=len(params))

    def __init__(self):
        Session.__init__(self)
        self.__connection = dbaccess.connect()

    def cursor(self):
        return Database.Cursor(self, self.__connection.cursor(), self.profiling)

    def commit(self):
        before = time.time()
        self.__connection.commit()
        after = time.time()
        self.recordProfiling("<commit>", after - before, 0)

    def rollback(self):
        before = time.time()
        self.__connection.rollback()
        after = time.time()
        self.recordProfiling("<rollback>", after - before, 0)

    def close(self):
        Session.close(self)
        self.__connection.close()

class NoSuchUser(base.Error):
    def __init__(self, name):
        super(NoSuchUser, self).__init__("No such user: %s" % name)
        self.name = name

class User():
    def __init__(self, user_id, name, email, fullname, status):
        self.id = user_id
        self.name = name
        self.email = email
        self.fullname = fullname
        self.status = status
        self.preferences = {}
        self.__resources = {}

    def __eq__(self, other):
        if self.isAnonymous(): return False
        elif isinstance(other, User):
            if other.isAnonymous(): return False
            else: return self.id == other.id
        elif isinstance(other, int):
            return self.id == other
        elif isinstance(other, str):
            return self.name == other
        else:
            raise base.Error, "invalid comparison"

    def __ne__(self, other):
        return not (self == other)

    def __int__(self):
        return self.id

    def __repr__(self):
        return "User(%r, %r, %r, %r)" % (self.id, self.name, self.email, self.fullname)

    def __hash__(self):
        return hash(self.id)

    @staticmethod
    def makeAnonymous():
        return User(None, None, None, None, 'anonymous')

    def isAnonymous(self):
        return self.status == 'anonymous'

    def hasRole(self, db, role):
        cursor = db.cursor()
        cursor.execute("SELECT 1 FROM userroles WHERE uid=%s AND role=%s", (self.id, role))
        return bool(cursor.fetchone())

    def loadPreferences(self, db):
        if not self.preferences:
            cursor = db.cursor()
            cursor.execute("""SELECT preferences.item, type, COALESCE(integer, default_integer), COALESCE(string, default_string)
                                FROM preferences
                     LEFT OUTER JOIN userpreferences ON (preferences.item=userpreferences.item
                                                     AND userpreferences.uid=%s)""",
                           (self.id,))

            for item, preference_type, integer, string in cursor:
                if preference_type == "boolean":
                    self.preferences[item] = bool(integer)
                elif preference_type == "integer":
                    self.preferences[item] = integer
                else:
                    self.preferences[item] = string

    def getPreference(self, db, item):
        if item not in self.preferences:
            cursor = db.cursor()
            cursor.execute("""SELECT type, COALESCE(integer, default_integer), COALESCE(string, default_string)
                                FROM preferences
                     LEFT OUTER JOIN userpreferences ON (preferences.item=userpreferences.item
                                                     AND userpreferences.uid=%s)
                               WHERE preferences.item=%s""", (self.id, item))
            row = cursor.fetchone()

            if not row: raise Exception, "invalid preference: %s" % item

            preference_type, integer, string = row

            if preference_type == "boolean":
                self.preferences[item] = bool(integer)
            elif preference_type == "integer":
                self.preferences[item] = integer
            else:
                self.preferences[item] = string

        return self.preferences[item]

    def setPreference(self, db, item, value):
        self.loadPreferences(db)
        if self.preferences[item] != value:
            cursor = db.cursor()
            cursor.execute("DELETE FROM userpreferences WHERE uid=%s AND item=%s", [self.id, item])
            cursor.execute("SELECT type FROM preferences WHERE item=%s", [item])

            value_type = cursor.fetchone()[0]

            if value_type in ('boolean', 'integer'):
                cursor.execute("INSERT INTO userpreferences (uid, item, integer) VALUES (%s, %s, %s)", [self.id, item, int(value)])
            else:
                cursor.execute("INSERT INTO userpreferences (uid, item, string) VALUES (%s, %s, %s)", [self.id, item, str(value)])

    def getDefaultRepository(self, db):
        return gitutils.Repository.fromName(db, self.getPreference(db, "defaultRepository"))

    def getResource(self, db, name):
        if name in self.__resources:
            return self.__resources[name]

        cursor = db.cursor()
        cursor.execute("SELECT revision, source FROM userresources WHERE uid=%s AND name=%s ORDER BY revision DESC FETCH FIRST ROW ONLY", (self.id, name))

        row = cursor.fetchone()

        if row and row[1] is not None:
            resource = self.__resources[name] = ("\"critic.rev.%d\"" % row[0], row[1])
            return resource

        path = os.path.join(configuration.paths.INSTALL_DIR, "resources", name)
        mtime = os.stat(path).st_mtime

        resource = self.__resources[name] = ("\"critic.mtime.%d\"" % mtime, open(path).read())
        return resource

    def getCriticURLs(self, db):
        url_types = self.getPreference(db, 'email.urlType').split(",")

        cursor = db.cursor()
        cursor.execute("SELECT key, url_prefix FROM systemidentities")

        url_prefixes = dict(cursor)

        return [url_prefixes[url_type] for url_type in url_types]

    def getFirstName(self):
        return self.fullname.split(" ")[0]

    def getJSConstructor(self, db=None):
        if self.isAnonymous():
            return "new User(null, null, null, null, null, { ui: {} }"
        if db:
            options = ("{ ui: { keyboardShortcuts: %s, resolveIssueWarning: %s, convertIssueToNote: %s, asynchronousReviewMarking: %s } }" %
                       ("true" if self.getPreference(db, "ui.keyboardShortcuts") else "false",
                        "true" if self.getPreference(db, "ui.resolveIssueWarning") else "false",
                        "true" if self.getPreference(db, "ui.convertIssueToNote") else "false",
                        "true" if self.getPreference(db, "ui.asynchronousReviewMarking") else "false"))
        else:
            options = "{ ui: {} }"
        return "new User(%d, %s, %s, %s, %s, %s)" % (self.id, jsify(self.name), jsify(self.email), jsify(self.fullname), jsify(self.status), options)

    def getJS(self, db=None, name="user"):
        return "var %s = %s;" % (name, self.getJSConstructor(db))

    def getAbsence(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT until FROM userabsence WHERE uid=%s", (self.id,))
        row = cursor.fetchone()
        return "absent until %04d-%02d-%02d" % (row[0].year, row[0].month, row[0].day)

    def retire(self, db):
        import review.utils
        review.utils.retireUser(db, self)

    @staticmethod
    def cache(db, user):
        storage = db.storage["User"]
        storage[user.id] = user
        if user.name: storage["n:" + user.name] = user
        if user.email: storage["e:" + user.email] = user
        return user

    @staticmethod
    def fromId(db, user_id):
        cached_user = db.storage["User"].get(user_id)
        if cached_user: return cached_user
        else:
            cursor = db.cursor()
            cursor.execute("SELECT name, email, fullname, status FROM users WHERE id=%s", (user_id,))
            row = cursor.fetchone()
            if not row: return None
            name, email, fullname, status = row
            return User.cache(db, User(user_id, name, email, fullname, status))

    @staticmethod
    def fromIds(db, user_ids):
        need_fetch = []
        cache = db.storage["User"]
        for user_id in user_ids:
            if user_id not in cache:
                need_fetch.append(user_id)
        if need_fetch:
            cursor = db.cursor()
            cursor.execute("SELECT id, name, email, fullname, status FROM users WHERE id=ANY (%s)", (need_fetch,))
            for user_id, name, email, fullname, status in cursor:
                User.cache(db, User(user_id, name, email, fullname, status))
        return [cache.get(user_id) for user_id in user_ids]

    @staticmethod
    def fromEmail(db, email):
        cached_user = db.storage["User"].get("e:" + email)
        if cached_user: return cached_user
        else:
            cursor = db.cursor()
            cursor.execute("SELECT id, name, fullname, status FROM users WHERE email=%s", (email,))
            row = cursor.fetchone()
            if not row: return None
            user_id, name, fullname, status = row
            return User.cache(db, User(user_id, name, email, fullname, status))

    @staticmethod
    def fromName(db, name):
        cached_user = db.storage["User"].get("n:" + name)
        if cached_user: return cached_user
        else:
            cursor = db.cursor()
            cursor.execute("SELECT id, email, fullname, status FROM users WHERE name=%s", (name,))
            row = cursor.fetchone()
            if not row: raise NoSuchUser, name
            user_id, email, fullname, status = row
            return User.cache(db, User(user_id, name, email, fullname, status))

def find_directory(db, path):
    path = path.strip("/")

    cursor = db.cursor()

    try:
        cursor.execute("SELECT finddirectory(%s)", (path,))
        directory_id = cursor.fetchone()[0]
        if directory_id is not None: return directory_id
    except: pass

    if "/" in path:
        directory, name = path.rsplit("/", 1)
        directory = find_directory(db, directory)
    else:
        directory, name = 0, path

    cursor.execute("INSERT INTO directories (directory, name) VALUES (%s, %s) RETURNING id", (directory, name))
    return cursor.fetchone()[0]

def is_directory(db, path):
    cursor = db.cursor()
    cursor.execute("SELECT finddirectory(%s)", (path,))

    directory_id = cursor.fetchone()[0]

    if directory_id is None: return False

    cursor.execute("SELECT 1 FROM files WHERE directory=%s LIMIT 1", (directory_id,))

    return bool(cursor.fetchone())

def is_file(db, path):
    cursor = db.cursor()
    cursor.execute("SELECT findfile(%s)", (path,))

    file_id = cursor.fetchone()[0]

    if file_id is None: return False

    cursor.execute("SELECT 1 FROM fileversions WHERE file=%s LIMIT 1", (file_id,))

    return bool(cursor.fetchone())

def find_file(db, path):
    path = path.lstrip("/")

    cursor = db.cursor()

    try:
        cursor.execute("SELECT findfile(%s)", (path,))
        file_id = cursor.fetchone()[0]
        if file_id is not None: return file_id
    except: pass

    if "/" in path:
        directory, name = path.rsplit("/", 1)
        directory = find_directory(db, directory)
    else:
        directory, name = 0, path

    cursor.execute("INSERT INTO files (directory, name) VALUES (%s, %s) RETURNING id", (directory, name))
    return cursor.fetchone()[0]

def find_files(db, files):
    for file in files:
        file.id = find_file(db, path=file.path)

def find_directory_file(db, path):
    path = path.strip("/")
    file_id = find_file(db, path)
    if "/" in path:
        directory_id = find_directory(db, path.rsplit("/", 1)[0])
    else:
        directory_id = 0
    return directory_id, file_id

def describe_directory(db, directory_id):
    cursor = db.cursor()
    cursor.execute("SELECT fulldirectoryname(%s)", (directory_id,))
    return cursor.fetchone()[0].rstrip("/")

def describe_file(db, file_id):
    cursor = db.cursor()
    cursor.execute("SELECT fullfilename(%s)", (file_id,))
    return cursor.fetchone()[0]

def explode_path(db, invalid=None, file_id=None, directory_id=None):
    assert invalid is None
    assert (file_id is None) != (directory_id is None)

    cursor = db.cursor()
    path = []

    if file_id is not None:
        cursor.execute("SELECT * FROM filepath(%s)", (file_id,))
    else:
        path.append(directory_id)
        if not directory_id: return path
        cursor.execute("SELECT * FROM directorypath(%s)", (directory_id,))

    for (directory_id,) in cursor:
        path.insert(0, directory_id)

    return path

def contained_files(db, directory_id):
    cursor = db.cursor()
    cursor.execute("SELECT file_out FROM containedfiles(%s)", (directory_id,))
    return [file_id for (file_id,) in cursor]

class ReviewState:
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

class Review:
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
        self.changesets = []
        self.commentchains = None
        self.applyfilters = applyfilters
        self.applyparentfilters = applyparentfilters
        self.filters = None
        self.relevant_files = None
        self.draft_status = None

    @staticmethod
    def isAccepted(db, review_id):
        cursor = db.cursor()

        cursor.execute("SELECT 1 FROM reviewfiles WHERE review=%s AND state='pending' LIMIT 1", (review_id,))
        if cursor.fetchone(): return False

        cursor.execute("SELECT 1 FROM commentchains WHERE review=%s AND type='issue' AND state='open' LIMIT 1", (review_id,))
        if cursor.fetchone(): return False

        return True

    def accepted(self, db):
        if self.state != 'open': return False
        else: return Review.isAccepted(db, self.id)

    def getReviewState(self, db):
        cursor = db.cursor()

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

    def containsCommit(self, db, commit):
        commit_id = None
        commit_sha1 = None

        if isinstance(commit, gitutils.Commit):
            if commit.id: commit_id = commit.id
            else: commit_sha1 = commit.sha1
        elif isinstance(commit, str):
            commit_sha1 = self.repository.revparse(commit)
        elif isinstance(commit, int):
            commit_id = commit
        else:
            raise TypeError

        cursor = db.cursor()

        if commit_id is not None:
            cursor.execute("""SELECT 1
                                FROM reviewchangesets
                                JOIN changesets ON (id=changeset)
                               WHERE reviewchangesets.review=%s
                                 AND changesets.child=%s""",
                           (self.id, commit_id))
        else:
            cursor.execute("""SELECT 1
                                FROM reviewchangesets
                                JOIN changesets ON (changesets.id=reviewchangesets.changeset)
                                JOIN commits ON (commits.id=changesets.child)
                               WHERE reviewchangesets.review=%s
                                 AND commits.sha1=%s""",
                           (self.id, commit_sha1))

        return cursor.fetchone() is not None

    def getCommentChains(self, db, user, skip=None):
        import review.comment
        import time

        if self.commentchains is None:
            if "commits" in skip and "lines" in skip:
                self.commentchains = review.comment.CommentChain.fromReview(db, self, user)
            else:
                cursor = db.cursor()
                if user: cursor.execute("SELECT id FROM commentchains WHERE review=%s AND (state!='draft' OR uid=%s) ORDER BY id DESC", [self.id, user.id])
                else: cursor.execute("SELECT id FROM commentchains WHERE review=%s AND state!='draft' ORDER BY id DESC", [self.id])
                self.commentchains = [review.comment.CommentChain.fromId(db, id, user, review=self, skip=skip) for (id,) in cursor.fetchall()]

        return self.commentchains

    def getJS(self):
        return "var review = critic.review = { id: %d, branch: { id: %d, name: %r }, owners: [ %s ], serial: %d };" % (self.id, self.branch.id, self.branch.name, ", ".join(owner.getJSConstructor() for owner in self.owners), self.serial)

    def getETag(self, db, user=None):
        etag = "review%d.serial%d" % (self.id, self.serial)

        if user:
            items = self.getDraftStatus(db, user)
            if any(items.values()):
                etag += ".draft%d" % hash(tuple(sorted(items.items())))

            cursor = db.cursor()
            cursor.execute("SELECT id FROM reviewrebases WHERE review=%s AND uid=%s AND new_head IS NULL", (self.id, user.id))
            row = cursor.fetchone()
            if row:
                etag += ".rebase%d" % row[0]

        return '"%s"' % etag

    def getURL(self, db, user=None, indent=0):
        indent = " " * indent

        if db and user:
            url_prefixes = user.getCriticURLs(db)
        else:
            url_prefixes = [getURLPrefix(db)]

        return "\n".join(["%s%s/r/%d" % (indent, url_prefix, self.id) for url_prefix in url_prefixes])

    def getRecipients(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT uid, include FROM reviewrecipientfilters WHERE review=%s ORDER BY uid ASC", (self.id,))

        included = set(owner.id for owner in self.owners)
        excluded = set()
        for uid, include in cursor:
            if include: included.add(uid)
            elif uid not in self.owners: excluded.add(uid)

        cursor.execute("SELECT uid FROM reviewusers WHERE review=%s", (self.id,))

        recipients = []
        for (user_id,) in cursor:
            if user_id in excluded: continue
            elif user_id not in included and 0 in excluded: continue

            user = User.fromId(db, user_id)
            if user.status != "retired":
                recipients.append(user)

        return recipients

    def getDraftStatus(self, db, user):
        if self.draft_status is None:
            import review.utils
            self.draft_status = review.utils.countDraftItems(db, user, self)
        return self.draft_status

    def incrementSerial(self, db):
        self.serial += 1
        db.cursor().execute("UPDATE reviews SET serial=%s WHERE id=%s", [self.serial, self.id])

    def close(self, db, user):
        self.serial += 1
        db.cursor().execute("UPDATE reviews SET state='closed', serial=%s, closed_by=%s WHERE id=%s", (self.serial, user.id, self.id))

    def drop(self, db, user):
        self.serial += 1
        db.cursor().execute("UPDATE reviews SET state='dropped', serial=%s, closed_by=%s WHERE id=%s", (self.serial, user.id, self.id))

    def reopen(self, db, user):
        self.serial += 1
        db.cursor().execute("UPDATE reviews SET state='open', serial=%s, closed_by=NULL WHERE id=%s", (self.serial, self.id))

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
        cursor = db.cursor()
        cursor.execute("SELECT directory, file, type, NULL, uid FROM reviewfilters WHERE review=%s", (self.id,))
        return cursor.fetchall() or None

    def getFilteredTails(self):
        commitset = CommitSet(self.branch.commits)
        return commitset.getFilteredTails(self.branch.repository)

    def getRelevantFiles(self, db, user):
        if not self.filters:
            from review.filters import Filters

            self.filters = Filters()
            self.filters.load(db, review=self)
            self.relevant_files = self.filters.getRelevantFiles(db, self)

            cursor = db.cursor()
            cursor.execute("SELECT assignee, file FROM fullreviewuserfiles WHERE review=%s", (self.id,))
            for user_id, file_id in cursor:
                self.relevant_files.setdefault(user_id, set()).add(file_id)

        return self.relevant_files.get(user.id, set())

    def getUserAssociation(self, db, user):
        cursor = db.cursor()

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
    def fromId(db, review_id, branch=None, load_commits=True, profiler=None):
        cursor = db.cursor()
        cursor.execute("SELECT type, branch, state, serial, summary, description, applyfilters, applyparentfilters FROM reviews WHERE id=%s", [review_id])
        row = cursor.fetchone()
        if not row: return None

        type, branch_id, state, serial, summary, description, applyfilters, applyparentfilters = row

        if profiler: profiler.check("Review.fromId: basic")

        if branch is None:
            branch = Branch.fromId(db, branch_id, load_review=False, load_commits=load_commits, profiler=profiler)

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

        if load_commits:
            review.branch.loadCommits(db)

            cursor.execute("""SELECT id
                                FROM reviewchangesets
                                JOIN changesets ON (id=changeset)
                               WHERE review=%s
                                 AND child=ANY (%s)""", (review_id, [commit.id for commit in review.branch.commits]))

            review.changesets = [changeset_id for (changeset_id,) in cursor.fetchall()]

            if profiler: profiler.check("Review.fromId: load commits")

        return review

    @staticmethod
    def fromBranch(db, branch):
        if branch:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM reviews WHERE branch=%s", [branch.id])
            row = cursor.fetchone()
            if not row: return None
            else: return Review.fromId(db, row[0], branch)
        else:
            return None

    @staticmethod
    def fromName(db, repository, name):
        return Review.fromBranch(db, Branch.fromName(db, repository, name))

    @staticmethod
    def fromArgument(db, argument):
        try:
            return Review.fromId(db, int(argument))
        except:
            branch = Branch.fromName(db, str(argument))
            if not branch: return None
            return Review.fromBranch(db, branch)

class Branch:
    def __init__(self, id, repository, name, head, base, tail, branch_type, review_id):
        self.id = id
        self.repository = repository
        self.name = name
        self.head = head
        self.base = base
        self.tail = tail
        self.type = branch_type
        self.review_id = review_id
        self.review = None
        self.commits = None

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id

    def contains(self, db, commit):
        cursor = db.cursor()
        if isinstance(commit, gitutils.Commit) and commit.id is not None:
            cursor.execute("SELECT 1 FROM reachable WHERE branch=%s AND commit=%s", [self.id, commit.id])
        else:
            cursor.execute("SELECT 1 FROM reachable, commits WHERE branch=%s AND commit=id AND sha1=%s", [self.id, str(commit)])
        return cursor.fetchone() is not None

    def getJSConstructor(self):
        if self.base:
            return "new Branch(%d, %s, %s)" % (self.id, jsify(self.name), self.base.getJSConstructor())
        else:
            return "new Branch(%d, %s, null)" % (self.id, jsify(self.name))

    def getJS(self):
        return "var branch = %s;" % self.getJSConstructor()

    def loadCommits(self, db):
        if self.commits is None:
            cursor = db.cursor()
            cursor.execute("SELECT commits.id, commits.sha1 FROM reachable, commits WHERE reachable.branch=%s AND reachable.commit=commits.id", [self.id])
            self.commits = []
            for commit_id, sha1 in cursor:
                self.commits.append(gitutils.Commit.fromSHA1(db, self.repository, sha1, commit_id=commit_id))

    def rebase(self, db, base):
        cursor = db.cursor()

        def findReachable(head, base_branch_id, force_include=set()):
            bases = [base_branch_id]

            while True:
                cursor.execute("SELECT base FROM branches WHERE id=%s", (bases[-1],))
                branch_id = cursor.fetchone()[0]
                if branch_id is None: break
                bases.append(branch_id)

            expression = "SELECT 1 FROM reachable, commits WHERE branch IN (%s) AND commit=id AND sha1=%%s" % ", ".join(["%s"] * len(bases))

            def exclude(sha1):
                cursor.execute(expression, bases + [sha1])
                return cursor.fetchone() is not None

            stack = [head.sha1]
            processed = set()
            values = []

            while stack:
                sha1 = stack.pop(0)

                if sha1 not in processed:
                    processed.add(sha1)

                    commit = gitutils.Commit.fromSHA1(db, self.repository, sha1)

                    if sha1 in force_include or not exclude(sha1):
                        values.append(commit.getId(db))

                        for sha1 in commit.parents:
                            if sha1 not in processed and (sha1 in force_include or not exclude(sha1)):
                                stack.append(sha1)

            return values

        cursor.execute("SELECT COUNT(*) FROM reachable WHERE branch=%s", (self.id,))
        old_count = cursor.fetchone()[0]

        if base.base and base.base.id == self.id:
            self.loadCommits(db)

            cursor.execute("SELECT count(*) FROM reachable WHERE branch=%s", (base.id,))
            base_old_count = cursor.fetchone()[0]

            base_reachable = findReachable(base.head, self.base.id, set([commit.sha1 for commit in self.commits]))
            base_new_count = len(base_reachable)

            cursor.execute("DELETE FROM reachable WHERE branch=%s", [base.id])
            cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", [(base.id, commit) for commit in base_reachable])
            cursor.execute("UPDATE branches SET base=%s WHERE id=%s", [self.base.id, base.id])

            base.base = self.base
            base.commits = None
        else:
            base_old_count = None
            base_new_count = None

        our_reachable = findReachable(self.head, base.id)
        new_count = len(our_reachable)

        cursor.execute("DELETE FROM reachable WHERE branch=%s", [self.id])
        cursor.executemany("INSERT INTO reachable (branch, commit) VALUES (%s, %s)", [(self.id, commit) for commit in our_reachable])
        cursor.execute("UPDATE branches SET base=%s WHERE id=%s", [base.id, self.id])

        self.base = base
        self.commits = None

        return old_count, new_count, base_old_count, base_new_count

    @staticmethod
    def fromId(db, branch_id, load_review=False, load_commits=True, profiler=None):
        cursor = db.cursor()
        cursor.execute("SELECT name, repository, head, base, tail, branches.type, review, reviews.id IS NOT NULL FROM branches LEFT OUTER JOIN reviews ON (branches.id=reviews.branch) WHERE branches.id=%s", [branch_id])
        row = cursor.fetchone()

        if not row: return None
        else:
            branch_name, repository_id, head_commit_id, base_branch_id, tail_commit_id, type, review_id, has_review = row

            if profiler: profiler.check("Branch.fromId: basic")

            repository = gitutils.Repository.fromId(db, repository_id)

            if profiler: profiler.check("Branch.fromId: repository")

            if load_commits:
                try: head_commit = gitutils.Commit.fromId(db, repository, head_commit_id)
                except: head_commit = None

                if profiler: profiler.check("Branch.fromId: head")
            else:
                head_commit = None

            if load_commits:
                base_branch = Branch.fromId(db, base_branch_id) if base_branch_id is not None else None

                if profiler: profiler.check("Branch.fromId: base")

                tail_commit = gitutils.Commit.fromId(db, repository, tail_commit_id) if tail_commit_id is not None else None

                if profiler: profiler.check("Branch.fromId: tail")
            else:
                base_branch = None
                tail_commit = None

            branch = Branch(branch_id, repository, branch_name, head_commit, base_branch, tail_commit, type, review_id)

            if has_review and load_review:
                branch.review = Review.fromBranch(db, branch)

                if profiler: profiler.check("Branch.fromId: review")

            return branch

    @staticmethod
    def fromName(db, repository, name):
        cursor = db.cursor()
        cursor.execute("SELECT id FROM branches WHERE repository=%s AND name=%s", (repository.id, name))
        row = cursor.fetchone()
        if not row: return None
        else: return Branch.fromId(db, row[0])

def getURLPrefix(db):
    cursor = db.cursor()
    cursor.execute("SELECT url_prefix FROM systemidentities WHERE name=%s", (configuration.base.SYSTEM_IDENTITY,))
    return cursor.fetchone()[0]
