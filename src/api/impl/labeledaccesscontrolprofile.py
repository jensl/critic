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
from . import apiobject
import dbutils

public_module = api.labeledaccesscontrolprofile
public_class = public_module.LabeledAccessControlProfile

class LabeledAccessControlProfile(apiobject.APIObject):
    wrapper_class = public_class

    def __init__(self, labels, profile_id):
        self.labels = tuple(labels.split("|"))
        self.__profile_id = profile_id

    def getAccessControlProfile(self, critic):
        return api.accesscontrolprofile.fetch(critic, self.__profile_id)

@LabeledAccessControlProfile.cached()
def fetch(critic, labels):
    cursor = critic.getDatabaseCursor()
    cursor.execute("""SELECT labels, profile
                        FROM labeledaccesscontrolprofiles
                       WHERE labels=%s""",
                   ("|".join(labels),))
    try:
        return next(LabeledAccessControlProfile.make(critic, cursor))
    except StopIteration:
        raise public_module.InvalidAccessControlProfileLabels(labels)

def fetchAll(critic, profile):
    cursor = critic.getDatabaseCursor()
    if profile is None:
        cursor.execute("""SELECT labels, profile
                            FROM labeledaccesscontrolprofiles
                        ORDER BY labels ASC""")
    else:
        cursor.execute("""SELECT labels, profile
                            FROM labeledaccesscontrolprofiles
                           WHERE profile=%s
                        ORDER BY labels ASC""",
                       (profile.id,))
    return list(LabeledAccessControlProfile.make(critic, cursor))
