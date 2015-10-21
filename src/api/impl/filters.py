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
import apiobject

class RepositoryFilter(apiobject.APIObject):
    wrapper_class = api.filters.RepositoryFilter

    def __init__(self, filter_id, subject_id, filter_type, path, repository_id,
                 delegate_string, repository=None):
        self.id = filter_id
        self.__subject_id = subject_id
        self.__subject = None
        self.type = filter_type
        self.path = path
        self.__repository_id = repository_id
        self.__repository = repository
        self.__delegate_string = delegate_string
        self.__delegates = None

    def getSubject(self, critic):
        if self.__subject is None:
            self.__subject = api.user.fetch(critic, user_id=self.__subject_id)
        return self.__subject

    def getRepository(self, critic):
        if self.__repository is None:
            self.__repository = api.repository.fetch(
                critic, repository_id=self.__repository_id)
        return self.__repository

    def getDelegates(self, critic):
        if self.__delegates is None:
            self.__delegates = frozenset(
                api.user.fetch(critic, name=name.strip())
                for name in filter(None, self.__delegate_string.split(",")))
        return self.__delegates

    def refresh(self, critic):
        cursor = critic.getDatabaseCursor()
        cursor.execute("""SELECT id, uid, type, path, repository, delegate
                            FROM filters
                           WHERE id=%s""",
                       (self.id,))
        row = cursor.fetchone()
        if row:
            return RepositoryFilter(*row)
        return self

def fetchRepositoryFilter(critic, filter_id):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT id, uid, type, path, repository, delegate
                        FROM filters
                       WHERE id=%s""",
                   (filter_id,))
    try:
        return next(RepositoryFilter.make(critic, cursor))
    except StopIteration:
        raise api.filters.InvalidRepositoryFilterId(filter_id)

class ReviewFilter(object):
    wrapper_class = api.filters.ReviewFilter

    def __init__(self, subject_id, filter_type, path, filter_id, review_id,
                 creator_id):
        self.__subject_id = subject_id
        self.__subject = None
        self.type = filter_type
        self.path = path
        self.id = filter_id
        self.__review_id = review_id
        self.__review = None
        self.__creator_id = creator_id
        self.__creator = None

    def getSubject(self, critic):
        if self.__subject is None:
            self.__subject = api.user.fetch(critic, user_id=self.__subject_id)
        return self.__subject

    def getReview(self, critic):
        if self.__review is None:
            self.__review = api.review.fetch(critic, review_id=self.__review_id)
        return self.__review

    def getCreator(self, critic):
        if self.__creator is None:
            self.__creator = api.user.fetch(critic, user_id=self.__creator_id)
        return self.__creator
