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

class ModifyLabeledAccessControlProfile(object):
    def __init__(self, transaction, labeled_profile):
        self.transaction = transaction
        self.labeled_profile = labeled_profile

    def delete(self):
        self.transaction.tables.add("labeledaccesscontrolprofiles")
        self.transaction.items.append(
            api.transaction.Query(
                """DELETE
                     FROM labeledaccesscontrolprofiles
                    WHERE labels=%s""",
                (str(self.labeled_profile),)))

    @staticmethod
    def create(transaction, labels, profile, callback=None):
        critic = transaction.critic

        labeled_profile = CreatedLabeledAccessControlProfile(critic, callback)

        transaction.tables.add("labeledaccesscontrolprofiles")
        transaction.items.append(
            api.transaction.Query(
                """INSERT
                     INTO labeledaccesscontrolprofiles (labels, profile)
                   VALUES (%s, %s)
                RETURNING labels""",
                ("|".join(sorted(labels)), profile.id),
                collector=labeled_profile))

        return ModifyLabeledAccessControlProfile(transaction, labeled_profile)

class CreatedLabeledAccessControlProfile(api.transaction.LazyAPIObject):
    def __init__(self, critic, callback=None):
        def fetch(critic, labels):
            return api.labeledaccesscontrolprofile.fetch(
                critic, labels.split("|"))
        super(CreatedLabeledAccessControlProfile, self).__init__(
            critic, fetch, callback)
