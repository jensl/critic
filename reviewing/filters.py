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

import dbutils

class Filters:
    def __init__(self):
        self.directories = {} # dict(directory_id -> dict(user_id -> tuple(filter_type, delegate)))
        self.files = {}       # dict(file_id      -> dict(user_id -> tuple(filter_type, delegate)))
        self.paths = {}       # dict(directory_id -> tuple(set(directory_id), set(file_id))

    def add(self, db, directory_id, file_id, filter_type, delegate, user_id):
        assert isinstance(directory_id, int)
        assert isinstance(file_id, int)
        assert isinstance(user_id, int)

        def addFile(file_id):
            for parent_directory_id in [0] + dbutils.explode_path(db, file_id=file_id):
                self.paths.setdefault(parent_directory_id, (set(), set()))[1].add(file_id)
            data = self.files[file_id] = {}
            return data

        def addDirectory(directory_id):
            for parent_directory_id in [0] + dbutils.explode_path(db, directory_id=directory_id)[:-1]:
                self.paths.setdefault(parent_directory_id, (set(), set()))[0].add(directory_id)
            data = self.directories[directory_id] = {}
            return data

        def clear(directory_id, user_id):
            data = self.paths.get(directory_id)
            if data:
                directories, files = data
                for child_directory_id in directories:
                    try: del self.directories[child_directory_id][user_id]
                    except: pass
                for file_id in files:
                    try: del self.files[file_id][user_id]
                    except: pass

        if file_id:
            data = self.files.get(file_id)
            if data is None:
                data = addFile(file_id)
        else:
            data = self.directories.get(directory_id)
            if data is None:
                data = addDirectory(directory_id)
            clear(directory_id, user_id)

        data[user_id] = (filter_type, delegate)

    def hasFilters(self):
        return bool(self.directories) or bool(self.files)

    def addFilters(self, db, filters, sort):
        if sort:
            sortedFilters = []
            for item in filters:
                specificity = len(dbutils.explode_path(db, directory_id=item[0]))
                if item[1]: specificity += 1
                sortedFilters.append((specificity, item))
            sortedFilters.sort(key=lambda item: item[0])
            filters = [item for specificity, item in sortedFilters]
        for item in filters:
            self.add(db, *item)

    class Review:
        def __init__(self, review_id, applyfilters, applyparentfilters, repository):
            self.id = review_id
            self.applyfilters = applyfilters
            self.applyparentfilters = applyparentfilters
            self.repository = repository

    def load(self, db, repository=None, review=None, recursive=False, user=None):
        assert (repository is None) != (review is None)

        cursor = db.cursor()

        if user is not None: user_filter = " AND uid=%d" % user.id
        else: user_filter = ""

        def loadGlobal(repository, recursive):
            if recursive and repository.parent:
                loadGlobal(repository.parent, recursive)

            cursor.execute("""SELECT filters.directory, filters.file, filters.type, filters.delegate, users.id
                                FROM filters
                                JOIN users ON (users.id=filters.uid)
                               WHERE filters.repository=%%s
                                 AND users.status!='retired'
                                     %s
                            ORDER BY specificity ASC""" % user_filter, (repository.id,))
            self.addFilters(db, cursor, sort=False)

        def loadReview(review):
            cursor.execute("""SELECT reviewfilters.directory, reviewfilters.file, reviewfilters.type, NULL, users.id
                                FROM reviewfilters
                                JOIN users ON (users.id=reviewfilters.uid)
                               WHERE reviewfilters.review=%%s
                                 AND users.status!='retired'
                                     %s""" % user_filter, (review.id,))
            self.addFilters(db, cursor, sort=True)

        if review:
            if review.applyfilters:
                loadGlobal(review.repository, review.applyparentfilters)
            loadReview(review)
        else:
            loadGlobal(repository, recursive)

    def __getUserFileAssociation(self, db, user_id, file_id):
        user_id = int(user_id)
        file_id = int(file_id)

        data = self.files.get(file_id)
        if data:
            data = data.get(user_id)
            if data: return data[0]

        for directory_id in reversed([0] + dbutils.explode_path(db, file_id=file_id)):
            data = self.directories.get(directory_id)
            if data:
                data = data.get(user_id)
                if data: return data[0]

        return None

    def isReviewer(self, db, user_id, file_id):
        return self.__getUserFileAssociation(db, user_id, file_id) == 'reviewer'

    def isWatcher(self, db, user_id, file_id):
        return self.__getUserFileAssociation(db, user_id, file_id) == 'watcher'

    def isRelevant(self, db, user_id, file_id):
        return self.__getUserFileAssociation(db, user_id, file_id) is not None

    def listUsers(self, db, file_id):
        users = {}

        for directory_id in [0] + dbutils.explode_path(db, file_id=file_id):
            data = self.directories.get(directory_id)
            if data: users.update(data)

        data = self.files.get(file_id)
        if data: users.update(data)

        return users

    def getRelevantFiles(self, db, review):
        cursor = db.cursor()
        cursor.execute("SELECT DISTINCT file FROM reviewfiles WHERE review=%s", (review.id,))

        relevant = {}

        for (file_id,) in cursor:
            for user_id in self.listUsers(db, file_id).keys():
                relevant.setdefault(user_id, set()).add(file_id)

        return relevant
