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

import os
import base

def _preferenceCacheKey(item, repository, filter_id):
    cache_key = item
    if filter_id is not None:
        cache_key += ":f%d" % filter_id
    if repository is not None:
        cache_key += ":r%d" % repository.id
    return cache_key

class NoSuchUser(base.Error):
    def __init__(self, name):
        super(NoSuchUser, self).__init__("No such user: %s" % name)
        self.name = name

class User(object):
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
        elif isinstance(other, basestring):
            return self.name == other
        else:
            raise base.Error, "invalid comparison"

    def __ne__(self, other):
        return not (self == other)

    def __int__(self):
        assert not self.isAnonymous()
        return self.id

    def __str__(self):
        assert not self.isAnonymous()
        return self.name

    def __repr__(self):
        return "User(%r, %r, %r, %r)" % (self.id, self.name, self.email, self.fullname)

    def __hash__(self):
        return hash(self.id)

    def isAnonymous(self):
        return self.status == 'anonymous'

    def hasRole(self, db, role):
        cursor = db.cursor()
        cursor.execute("SELECT 1 FROM userroles WHERE uid=%s AND role=%s", (self.id, role))
        return bool(cursor.fetchone())

    def loadPreferences(self, db):
        if not self.preferences:
            cursor = db.cursor()
            cursor.execute("""SELECT item, type, integer, string
                                FROM preferences
                                JOIN userpreferences USING (item)
                               WHERE (uid=%s OR uid IS NULL)
                                 AND repository IS NULL
                                 AND filter IS NULL
                            ORDER BY uid NULLS LAST""",
                           (self.id,))

            for item, preference_type, integer, string in cursor:
                cache_key = _preferenceCacheKey(item, None, None)
                if cache_key not in self.preferences:
                    if preference_type == "boolean":
                        self.preferences[cache_key] = bool(integer)
                    elif preference_type == "integer":
                        self.preferences[cache_key] = integer
                    else:
                        self.preferences[cache_key] = string

    @staticmethod
    def fetchPreference(db, item, user=None, repository=None, filter_id=None):
        cursor = db.cursor()
        cursor.execute("SELECT type FROM preferences WHERE item=%s", (item,))
        row = cursor.fetchone()
        if not row:
            raise base.ImplementationError("invalid preference: %s" % item)
        preference_type = row[0]

        arguments = [item]
        where = ["item=%s"]
        order_by = []

        if preference_type in ("boolean", "integer"):
            value_column = "integer"
        else:
            value_column = "string"

        if user is not None and not user.isAnonymous():
            arguments.append(user.id)
            where.append("uid=%s OR uid IS NULL")
            order_by.append("uid NULLS LAST")
        else:
            where.append("uid IS NULL")

        if repository is not None:
            arguments.append(repository.id)
            where.append("repository=%s OR repository IS NULL")
            order_by.append("repository NULLS LAST")
        else:
            where.append("repository IS NULL")

        if filter_id is not None:
            arguments.append(filter_id)
            where.append("filter=%s OR filter IS NULL")
            order_by.append("filter NULLS LAST")
        else:
            where.append("filter IS NULL")

        query = ("""SELECT %(value_column)s
                      FROM userpreferences
                     WHERE %(where)s"""
                 % { "value_column": value_column,
                     "where": " AND ".join("(%s)" % condition
                                           for condition in where) })

        if order_by:
            query += " ORDER BY " + ", ".join(order_by)

        query += " LIMIT 1"

        cursor.execute(query, arguments)
        row = cursor.fetchone()
        if not row:
            raise base.ImplementationError(
                "invalid preference read: %s (no value found)" % item)
        (value,) = row
        if preference_type == "boolean":
            return bool(value)
        return value

    @staticmethod
    def storePreference(db, item, value, user=None, repository=None, filter_id=None):
        # A preference value can be set for either a repository or a filter, but
        # not for both at the same time.  A filter implies a repository anyway,
        # so there would be no point.
        assert repository is None or filter_id is None
        assert filter_id is None or user is not None

        # If all are None, we'd be deleting the global default and not setting a
        # new one, which would be bad.
        if value is None and user is None \
                and repository is None and filter is None:
            raise base.ImplementationError("attempted to delete global default")

        if User.fetchPreference(db, item, user, repository, filter_id) != value:
            cursor = db.cursor()

            arguments = [item]
            where = ["item=%s"]

            user_id = repository_id = None

            if user is not None:
                user_id = user.id
                arguments.append(user_id)
                where.append("uid=%s")
            else:
                where.append("uid IS NULL")

            if repository is not None:
                repository_id = repository.id
                arguments.append(repository_id)
                where.append("repository=%s")
            else:
                where.append("repository IS NULL")

            if filter_id is not None:
                arguments.append(filter_id)
                where.append("filter=%s")
            else:
                where.append("filter IS NULL")

            query = ("DELETE FROM userpreferences WHERE %s"
                     % (" AND ".join("(%s)" % condition
                                     for condition in where)))

            cursor.execute(query, arguments)

            if value is not None:
                cursor.execute("SELECT type FROM preferences WHERE item=%s", (item,))

                (value_type,) = cursor.fetchone()
                integer = string = None

                if value_type == "boolean":
                    value = bool(value)
                    integer = int(value)
                elif value_type == "integer":
                    integer = value = int(value)
                else:
                    string = value = str(value)

                cursor.execute("""INSERT INTO userpreferences (item, uid, repository, filter, integer, string)
                                       VALUES (%s, %s, %s, %s, %s, %s)""",
                               (item, user_id, repository_id, filter_id, integer, string))

            if user is not None:
                cache_key = _preferenceCacheKey(item, repository, filter_id)
                if cache_key in user.preferences:
                    del user.preferences[cache_key]

            return True
        else:
            return False

    def getPreference(self, db, item, repository=None, filter_id=None):
        cache_key = _preferenceCacheKey(item, repository, filter_id)

        if cache_key not in self.preferences:
            self.preferences[cache_key] = User.fetchPreference(
                db, item, self, repository, filter_id)

        return self.preferences[cache_key]

    def setPreference(self, db, item, value, repository=None, filter_id=None):
        return User.storePreference(db, item, value, self, repository, filter_id)

    def getDefaultRepository(self, db):
        import gitutils

        default_repo = self.getPreference(db, "defaultRepository")
        if not default_repo:
            cursor = db.cursor()
            cursor.execute("SELECT COUNT(*) FROM repositories")

            repo_count = cursor.fetchone()[0]
            if repo_count == 1:
                cursor.execute("SELECT name FROM repositories")
                default_repo = cursor.fetchone()[0]

        return gitutils.Repository.fromName(db, default_repo)

    def getResource(self, db, name):
        import configuration

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

    def adjustTimestamp(self, db, timestamp):
        import dbutils.timezones
        return dbutils.timezones.adjustTimestamp(db, timestamp, self.getPreference(db, "timezone"))

    def formatTimestamp(self, db, timestamp):
        import dbutils.timezones
        return dbutils.timezones.formatTimestamp(db, timestamp, self.getPreference(db, "timezone"))

    def getCriticURLs(self, db):
        url_types = self.getPreference(db, 'email.urlType').split(",")

        cursor = db.cursor()
        cursor.execute("""SELECT key, anonymous_scheme, authenticated_scheme, hostname
                            FROM systemidentities""")

        url_prefixes = dict((row[0], row[1:]) for row in cursor)
        urls = []

        for url_type in url_types:
            if url_prefixes.has_key(url_type):
                anonymous_scheme, authenticated_scheme, hostname = url_prefixes[url_type]
                if self.isAnonymous():
                    scheme = anonymous_scheme
                else:
                    scheme = authenticated_scheme
                urls.append("%s://%s" % (scheme, hostname))

        return urls

    def getFirstName(self):
        return self.fullname.split(" ")[0]

    def getJSConstructor(self, db=None):
        from htmlutils import jsify
        if self.isAnonymous():
            return "new User(null, null, null, null, null, { ui: {} })"
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

    def getJSON(self):
        return { "id": self.id,
                 "name": self.name,
                 "email": self.email,
                 "displayName": self.fullname }

    def getAbsence(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT until FROM userabsence WHERE uid=%s", (self.id,))
        row = cursor.fetchone()
        if row[0] is None:
            return "absent"
        else:
            return "absent until %04d-%02d-%02d" % (row[0].year, row[0].month, row[0].day)

    @staticmethod
    def cache(db, user):
        storage = db.storage["User"]
        storage[user.id] = user
        if user.name: storage["n:" + user.name] = user
        if user.email: storage["e:" + user.email] = user
        return user

    @staticmethod
    def makeAnonymous():
        return User(None, None, None, None, 'anonymous')

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

    @staticmethod
    def create(db, name, fullname, email, password=None, status="current"):
        cursor = db.cursor()
        cursor.execute("""INSERT INTO users (name, fullname, email, password, status)
                               VALUES (%s, %s, %s, %s, %s)
                            RETURNING id""",
                       (name, fullname, email, password, status))
        user = User.fromId(db, cursor.fetchone()[0])
        if email:
            cursor.execute("""INSERT INTO usergitemails (email, uid)
                                   VALUES (%s, %s)""",
                           (email, user.id))
        return user
