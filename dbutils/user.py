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

            if not row: raise base.ImplementationError("invalid preference: %s" % item)

            preference_type, integer, string = row

            if preference_type == "boolean":
                self.preferences[item] = bool(integer)
            elif preference_type == "integer":
                self.preferences[item] = integer
            else:
                self.preferences[item] = string

        return self.preferences[item]

    def setPreference(self, db, item, value):
        if self.getPreference(db, item) != value:
            cursor = db.cursor()
            cursor.execute("DELETE FROM userpreferences WHERE uid=%s AND item=%s", [self.id, item])
            cursor.execute("SELECT type FROM preferences WHERE item=%s", [item])

            value_type = cursor.fetchone()[0]

            if value_type in ('boolean', 'integer'):
                cursor.execute("INSERT INTO userpreferences (uid, item, integer) VALUES (%s, %s, %s)", [self.id, item, int(value)])
            else:
                cursor.execute("INSERT INTO userpreferences (uid, item, string) VALUES (%s, %s, %s)", [self.id, item, str(value)])

            self.preferences[item] = value

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

    def getCriticURLs(self, db):
        url_types = self.getPreference(db, 'email.urlType').split(",")

        cursor = db.cursor()
        cursor.execute("SELECT key, url_prefix FROM systemidentities")

        url_prefixes = dict(cursor)

        return [url_prefixes[url_type] for url_type in url_types]

    def getFirstName(self):
        return self.fullname.split(" ")[0]

    def getJSConstructor(self, db=None):
        from htmlutils import jsify
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
