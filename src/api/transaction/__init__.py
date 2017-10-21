# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

class Transaction(object):
    def __init__(self, critic):
        self.critic = critic
        self.tables = set()
        self.items = Queries()
        self.callbacks = []

    def modifyUser(self, subject):
        from .user import ModifyUser
        assert isinstance(subject, api.user.User)
        api.PermissionDenied.raiseUnlessUser(self.critic, subject)
        return ModifyUser(self, subject)

    def modifyAccessToken(self, access_token):
        from .accesstoken import ModifyAccessToken, CreatedAccessToken
        assert isinstance(access_token, (api.accesstoken.AccessToken,
                                         CreatedAccessToken))
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessToken(self, access_token)

    def createAccessControlProfile(self, callback=None):
        from .accesscontrolprofile import ModifyAccessControlProfile
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessControlProfile.create(self, callback)

    def modifyAccessControlProfile(self, profile):
        from .accesscontrolprofile import ModifyAccessControlProfile
        assert isinstance(
            profile, api.accesscontrolprofile.AccessControlProfile)
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        return ModifyAccessControlProfile(self, profile)

    def createLabeledAccessControlProfile(self, labels, profile, callback=None):
        from .labeledaccesscontrolprofile \
            import ModifyLabeledAccessControlProfile
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        assert isinstance(
            profile, api.accesscontrolprofile.AccessControlProfile)
        return ModifyLabeledAccessControlProfile.create(
            self, labels, profile, callback)

    def modifyLabeledAccessControlProfile(self, labeled_profile):
        from .labeledaccesscontrolprofile \
            import ModifyLabeledAccessControlProfile
        api.PermissionDenied.raiseUnlessAdministrator(self.critic)
        assert isinstance(
            labeled_profile,
            api.labeledaccesscontrolprofile.LabeledAccessControlProfile)
        return ModifyLabeledAccessControlProfile(self, labeled_profile)

    def modifyReview(self, review):
        from .review import ModifyReview
        assert isinstance(review, api.review.Review)
        return ModifyReview(self, review)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and exc_val is None and exc_tb is None:
            self.__commit()
        return False

    def __commit(self):
        if not self.items:
            return
        try:
            with self.critic.getUpdatingDatabaseCursor(*self.tables) as cursor:
                for item in self.items:
                    item(self.critic, cursor)
                for callback in self.callbacks:
                    callback()
        finally:
            self.critic._impl.transactionEnded(self.critic, self.tables)

class Query(object):
    def __init__(self, statement, *values, **kwargs):
        self.statement = statement
        self.__values = list(values)
        self.collector = kwargs.get("collector")

    def merge(self, query):
        if self.statement == query.statement \
                and not self.collector \
                and not query.collector:
            self.__values.extend(query.__values)
            return True
        return False

    @property
    def values(self):
        def evaluate(value):
            if isinstance(value, LazyValue):
                return value.evaluate()
            elif isinstance(value, (set, list, tuple)):
                return [evaluate(element) for element in value]
            else:
                return value

        for values in self.__values:
            yield evaluate(values)

    def __call__(self, critic, cursor):
        if self.collector:
            for values in self.values:
                cursor.execute(self.statement, values)
                for row in cursor:
                    self.collector(*row)
        else:
            cursor.executemany(self.statement, self.values)

class Queries(list):
    def append(self, query):
        if self and self[-1].merge(query):
            return
        super(Queries, self).append(query)

    def extend(self, queries):
        raise Exception("Append queries one at a time!")

class LazyValue(object):
    def evaluate(self):
        raise Exception("LazyValue.evaluate() must be implemented!")

class LazyInt(LazyValue):
    def __init__(self, source):
        self.source = source
    def evaluate(self):
        return self.source()

class LazyStr(LazyValue):
    def __init__(self, source):
        self.source = source
    def evaluate(self):
        return self.source()

class LazyObject(LazyValue):
    def __init__(self, callback=None):
        self.object_id = None
        self.callback = callback
    def __call__(self, object_id):
        self.object_id = object_id
        if self.callback:
            self.callback(self)
    @property
    def id(self):
        return LazyInt(self.evaluate)
    def evaluate(self):
        assert self.object_id is not None
        return self.object_id

class LazyAPIObject(LazyObject):
    def __init__(self, critic, fetch, callback=None):
        super(LazyAPIObject, self).__init__(
            callback=self.callback_wrapper if callback else None)
        self.critic = critic
        self.__fetch = fetch
        self.__callback = callback
    def fetch(self):
        return self.__fetch(self.critic, self.evaluate())
    @staticmethod
    def callback_wrapper(self):
        self.__callback(self.fetch())
