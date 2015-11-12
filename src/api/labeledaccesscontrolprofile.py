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

class LabeledAccessControlProfileError(api.APIError):
    """Base exception for all errors related to the LabeledAccessControlProfile
       class"""
    pass

class InvalidAccessControlProfileLabels(LabeledAccessControlProfileError):
    """Raised when an invalid label set is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidAccessControlProfileLabels, self).__init__(
            "Invalid labels: %s" % "|".join(value))
        self.value = value

class LabeledAccessControlProfile(api.APIObject):
    """Representation of a labeled access control profile selector"""

    RULE_VALUES = frozenset(["allow", "deny"])

    def __str__(self):
        return "|".join(self.labels)
    def __hash__(self):
        return hash(str(self))
    def __eq__(self, other):
        return str(self) == str(other)

    @property
    def labels(self):
        """The labels for which the access control profile is selected"""
        return self._impl.labels

    @property
    def profile(self):
        """The access control profile that is selected"""
        return self._impl.getAccessControlProfile(self.critic)

def fetch(critic, labels):
    """Fetch an LabeledAccessControlProfile object for the given labels"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    labels = tuple(sorted(str(label) for label in labels))
    return api.impl.labeledaccesscontrolprofile.fetch(critic, labels)

def fetchAll(critic, profile=None):
    """Fetch LabeledAccessControlProfile objects for all labeled profiles
       selectors in the system"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert profile is None \
        or isinstance(profile, api.accesscontrolprofile.AccessControlProfile)
    return api.impl.labeledaccesscontrolprofile.fetchAll(critic, profile)
