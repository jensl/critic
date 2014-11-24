# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
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

import api
import dbutils

class User(object):
    def __init__(self, user_id, name, fullname, status, email):
        self.id = user_id
        self.name = name
        self.fullname = fullname
        self.status = status
        self.email = email

        # Things that are fetched on demand.
        self.__internal = None

    def isAnonymous(self):
        return self.id is None

    def getInternal(self, critic):
        if not self.__internal:
            if self.isAnonymous():
                self.__internal = dbutils.User.makeAnonymous()
            else:
                self.__internal = dbutils.User.fromId(
                    critic.getDatabase(), self.id)
        return self.__internal

    def getPrimaryEmails(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT useremails.email,
                                 useremails.id=users.email,
                                 useremails.verified
                            FROM useremails
                            JOIN users ON (users.id=useremails.uid)
                           WHERE useremails.uid=%s
                        ORDER BY useremails.id ASC""",
                       (self.id,))
        return [api.user.User.PrimaryEmail(address, bool(selected),
                                           dbutils.boolean(verified))
                for address, selected, verified in cursor]

    def getGitEmails(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT email
                            FROM usergitemails
                           WHERE uid=%s""",
                       (self.id,))
        return set(email for (email,) in cursor)

    def getRepositoryFilters(self, critic):
        all_repositories = {}
        filters = {}

        def processRepository(repository_id):
            if repository_id not in all_repositories:
                all_repositories[repository_id] = api.repository.fetch(
                    critic, repository_id=repository_id)
            return all_repositories[repository_id]

        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT uid, type, path, id, repository, delegate
                            FROM filters
                           WHERE uid=%s
                        ORDER BY id ASC""",
                       (self.id,))

        for subject_id, filter_type, path, filter_id, repository_id, delegate_string in cursor:
            repository = processRepository(repository_id)
            filters.setdefault(repository, []).append(
                api.filters.RepositoryFilter(
                    critic,
                    api.impl.filters.RepositoryFilter(
                        subject_id, filter_type, path, filter_id, repository_id,
                        delegate_string, repository=repository)))

        return filters

    def hasRole(self, critic, role):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT uid
                            FROM roles
                 LEFT OUTER JOIN userroles ON (userroles.role=roles.name
                                           AND userroles.uid=%s)
                           WHERE name=%s""",
                       (self.id, role))
        row = cursor.fetchone()
        if row:
            return row[0] is not None
        raise api.user.InvalidRole(role)

    def getPreference(self, critic, item, user, repository):
        cursor = critic.getDatabaseCursor()
        cursor.execute("SELECT type FROM preferences WHERE item=%s", (item,))
        row = cursor.fetchone()
        if not row:
            raise api.preference.InvalidPreferenceItem(item)
        preference_type = row[0]

        arguments = [item]
        where = ["item=%s"]

        if preference_type in ("boolean", "integer"):
            column = "integer"
        else:
            column = "string"

        if not self.isAnonymous():
            arguments.append(user.id)
            where.append("uid=%s OR uid IS NULL")
        else:
            where.append("uid IS NULL")

        if repository is not None:
            arguments.append(repository.id)
            where.append("repository=%s OR repository IS NULL")
        else:
            where.append("repository IS NULL")

        where = " AND ".join("(%s)" % condition for condition in where)

        query = ("""SELECT %(column)s, uid, repository
                      FROM userpreferences
                     WHERE %(where)s"""
                 % { "column": column, "where": where })

        cursor.execute(query, arguments)

        row = sorted(cursor, key=lambda row: row[1:])[-1]
        value, user_id, repository_id = row

        if preference_type == "boolean":
            value = bool(value)

        if user_id is None:
            user = None
        if repository_id is None:
            repository = None

        return api.preference.Preference(item, value, user, repository)

    def wrap(self, critic):
        return api.user.User(critic, self)

def make(critic, args):
    for user_id, name, fullname, status, email in args:
        def callback():
            return User(user_id, name, fullname, status, email).wrap(critic)
        yield critic._impl.cached(api.user.User, user_id, callback)

def fetch(critic, user_id, name):
    try:
        return fetchMany(critic,
                         user_ids=None if user_id is None else [user_id],
                         names=None if name is None else [name])[0]
    except api.user.InvalidUserIds as error:
        raise api.user.InvalidUserId(error.values[0])
    except api.user.InvalidUserNames as error:
        raise api.user.InvalidUserName(error.values[0])

def fetchMany(critic, user_ids, names):
    return_type = list

    if user_ids is not None:
        if isinstance(user_ids, set):
            return_type = set
        where_column = "users.id"
        values = [int(user_id) for user_id in user_ids]
        column_index = 0
    else:
        if isinstance(names, set):
            return_type = set
        where_column = "name"
        values = [str(name) for name in names]
        column_index = 1

    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT users.id, name, fullname, status, useremails.email
                        FROM users
             LEFT OUTER JOIN useremails ON (useremails.id=users.email
                                        AND (useremails.verified IS NULL
                                          OR useremails.verified))
                       WHERE """ + where_column + """=ANY (%s)""",
                   (values,))
    rows = cursor.fetchall()

    if len(rows) < len(values):
        found = set(row[column_index] for row in rows)
        if user_ids is not None:
            exception_type = api.user.InvalidUserIds
        else:
            exception_type = api.user.InvalidUserNames
        values = [value for value in values if value not in found]
        raise exception_type(values)

    rows = dict((row[column_index], row) for row in rows)
    return return_type(make(critic, (rows[key] for key in values)))

def fetchAll(critic, status):
    cursor = critic.getDatabaseCursor()
    if status is None:
        condition = ""
        values = ()
    else:
        condition = " WHERE status IN (%s)" % ", ".join(["%s"] * len(status))
        values = tuple(status)
    cursor.execute("""SELECT users.id, name, fullname, status, useremails.email
                        FROM users
             LEFT OUTER JOIN useremails ON (useremails.id=users.email
                                        AND (useremails.verified IS NULL
                                          OR useremails.verified))
                       """ + condition + """
                    ORDER BY users.id""",
                   values)
    return list(make(critic, cursor))

def anonymous(critic):
    def callback():
        return User(None, None, None, "anonymous", None).wrap(critic)
    return critic._impl.cached(api.user.User, None, callback)
