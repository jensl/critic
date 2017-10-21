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

from operation import (Operation, OperationResult, OperationFailure,
                       OperationError, Optional, User, Repository)

import dbutils
import gitutils

class SaveSettings(Operation):
    def __init__(self):
        super(SaveSettings, self).__init__(
            { "subject": Optional(User),
              "repository": Optional(Repository),
              "filter_id": Optional(int),
              "settings": [{ "item": str,
                             "value": Optional({bool, int, str}) }],
              "defaults": Optional(bool) })

    def process(self, db, user, settings, subject=None, repository=None, filter_id=None, defaults=False):
        if repository is not None and filter_id is not None:
            raise OperationError("invalid input: both 'repository' and 'filter_id' set")

        if (subject and subject != user) or defaults:
            Operation.requireRole(db, "administrator", user)
        else:
            subject = user

        cursor = db.cursor()

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
            elif row[0] != subject.id:
                raise OperationFailure(
                    code="invalidfilter",
                    title="The filter belongs to someone else!",
                    message=("What are you up to?"))

        saved_settings = []

        for setting in settings:
            item = setting["item"]
            value = setting.get("value")

            if dbutils.User.storePreference(db, item, value, subject,
                                            repository, filter_id):
                saved_settings.append(setting["item"])

        db.commit()

        return OperationResult(saved_settings=sorted(saved_settings))
