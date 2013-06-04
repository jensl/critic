# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Jens Lindström, Opera Software ASA
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

from operation import Operation, OperationResult, OperationFailure, OperationError, Optional

import dbutils
import gitutils

class SaveSettings(Operation):
    def __init__(self):
        super(SaveSettings, self).__init__(
            { "user_id": Optional(int),
              "repository_id": Optional(int),
              "filter_id": Optional(int),
              "settings": [{ "item": str,
                             "value": Optional(set([bool, int, str])) }] })

    def process(self, db, user, settings, user_id=None, repository_id=None, filter_id=None):
        if repository_id is not None and filter_id is not None:
            raise OperationError("invalid input: both 'repository_id' and 'filter_id' set")

        if user_id is None:
            affected_user = user
        elif user_id != user.id:
            Operation.requireRole(db, "administrator", user)
            if user_id == -1:
                affected_user = None
            else:
                affected_user = dbutils.User.fromId(db, user_id)

        cursor = db.cursor()
        repository = None

        if filter_id is not None:
            # Check that the filter exists and that it's one of the user's
            # filters (or that the user has the administrator role.)
            cursor.execute("SELECT uid FROM filters WHERE id=%s", (filter_id,))
            row = cursor.fetchone()
            if not row:
                raise OperationFailure(
                    code="nosuchfilter",
                    title="No such filter!",
                    message=("Maybe the filter has been deleted since you "
                             "loaded this page?"))
            elif row[0] != affected_user.id:
                raise OperationFailure(
                    code="invalidfilter",
                    title="The filter belongs to someone else!",
                    message=("What are you up to?"))
        elif repository_id is not None:
            repository = gitutils.Repository.fromId(db, repository_id)

        saved_settings = []

        for setting in settings:
            item = setting["item"]
            value = setting.get("value")

            if dbutils.User.storePreference(db, item, value, affected_user,
                                            repository, filter_id):
                saved_settings.append(setting["item"])

        db.commit()

        return OperationResult(saved_settings=sorted(saved_settings))
