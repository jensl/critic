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

class UserError(api.APIError):
    """Base exception for all errors related to the User class"""
    pass

class InvalidUserIds(UserError):
    """Raised when one or more invalid user ids is used"""

    def __init__(self, values):
        """Constructor"""
        super(InvalidUserIds, self).__init__("Invalid user ids: %r" % values)
        self.values = values

class InvalidUserNames(UserError):
    """Raised when one or more invalid user names is used"""

    def __init__(self, values):
        """Constructor"""
        super(InvalidUserNames, self).__init__(
            "Invalid user names: %r" % values)
        self.values = values

class InvalidRole(UserError):
    """Raised when an invalid role is used"""

    def __init__(self, role):
        """Constructor"""
        super(InvalidRole, self).__init__("Invalid role: %r" % role)
        self.role = role

class InvalidStatus(UserError):
    """Raised when an invalid user status is used"""

    def __init__(self, status):
        """Constructor"""
        super(InvalidStatus, self).__init__("Invalid user status: %r" % status)
        self.status = status

class User(api.APIObject):
    """Representation of a Critic user"""

    STATUS_VALUES = frozenset(["current", "absent", "retired"])

    def __int__(self):
        return self.id
    def __hash__(self):
        return hash(int(self))
    def __eq__(self, other):
        return int(self) == int(other)

    @property
    def id(self):
        """The user's unique id"""
        return self._impl.id

    @property
    def name(self):
        """The user's unique username"""
        return self._impl.name

    @property
    def fullname(self):
        """The user's full name"""
        return self._impl.fullname

    @property
    def status(self):
        """The user's status

           For regular users, the value is one of the strings in the
           User.STATUS_VALUES set.

           For the anonymous user, the value is "anonymous".
           For the Critic system user, the value is "system"."""
        return self._impl.status

    @property
    def is_anonymous(self):
        """True if this object represents an anonymous user"""
        return self.id is None

    @property
    def email(self):
        """The user's selected primary email address

           If the user has no primary email address or if the selected primary
           email address is unverified, this attribute's value is None."""
        return self._impl.email

    class PrimaryEmail(object):
        """Primary email address

           The 'address' attribute is the email address as a string.

           The 'selected' attribute is True if this is the user's currently
           selected primary email address.

           The 'verified' attribute is False if the address is unverified and
           shouldn't be used until it has been verified, True if the address has
           been verified by us, and None if it hasn't been verified but can be
           used anyway."""

        def __init__(self, address, selected, verified):
            self.address = address
            self.selected = selected
            self.verified = verified

    @property
    def primary_emails(self):
        """The user's primary email addresses

           The value is a list of PrimaryEmail objects."""
        return self._impl.getPrimaryEmails(self.critic)

    @property
    def git_emails(self):
        """The user's "git" email addresses

           The value is a set of strings.

           These addresses are used to identify the user as author or committer
           of Git commits by matching the email address in the commit's meta
           data."""
        return self._impl.getGitEmails(self.critic)

    @property
    def repository_filters(self):
        """The user's repository filters

           The value is a dictionary mapping api.repository.Repository objects
           to lists of api.filters.RepositoryFilter objects."""
        return self._impl.getRepositoryFilters(self.critic)

    @property
    def json(self):
        """A dictionary suitable for JSON encoding"""
        return { "id": self.id,
                 "name": self.name,
                 "fullname": self.fullname,
                 "email": self.email,
                 "gitEmails": sorted(self.git_emails),
                 "isAnonymous": self.is_anonymous }

    def hasRole(self, role):
        """Return True if the user has the named role

           If the argument is not a valid role name, an InvalidRole exception is
           raised."""
        return self._impl.hasRole(self.critic, role)

    def getPreference(self, item, repository=None):
        """Fetch the user's preference setting for 'item'

           The setting is returned as an api.preference.Preference object, whose
           'user' and 'repository' attributes can be used to determine whether
           there was a per-user and/or per-repository override, or if a system
           default value was used.

           If 'repository' is not None, fetch a per-repository override if there
           is one."""
        assert (repository is None or
                isinstance(repository, api.repository.Repository))
        return self._impl.getPreference(self.critic, item, self, repository)

def fetch(critic, user_id=None, name=None):
    """Fetch a User object with the given user id or name

       Exactly one of the 'user_id' and 'name' arguments can be used.

       Exceptions:

         InvalidUserIds: if 'user_id' is used and is not a valid user id.
         InvalidUserNames: if 'name' is used and is not a valid user name."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (user_id is None) != (name is None)
    return api.impl.user.fetch(critic, user_id, name)

def fetchMany(critic, user_ids=None, names=None):
    """Fetch many User objects with given user ids or names

       Exactly one of the 'user_ids' and 'names' arguments can be used.

       If the value of the provided 'user_ids' or 'names' argument is a set, the
       return value is a also set of User objects, otherwise it is a list of
       User objects, in the same order as the argument sequence.

       Exceptions:

         InvalidUserIds: if 'user_ids' is used and any element in it is not a
                         valid user id.
         InvalidUserNames: if 'names' is used and any element in it is not a
                           valid user name."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (user_ids is None) != (names is None)
    return api.impl.user.fetchMany(critic, user_ids, names)

def fetchAll(critic, status=None):
    """Fetch User objects for all users of the system

       If |status| is not None, it must be one of the user statuses "current",
       "absent" or "retired", or an iterable containing one or more of those
       strings."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.user.fetchAll(critic, status)

def anonymous(critic):
    """Fetch a User object representing an anonymous user"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    return api.impl.user.anonymous(critic)
