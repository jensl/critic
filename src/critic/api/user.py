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

"""The `User` class with associated exceptions and functions.

Use `fetch()` to fetch/lookup a single user entry from the database,
`fetchMany()` to fetch/lookup multiple user entries in a single call, or
`fetchAll()` to fetch all user entries, possibly filtered to include only users
with a certain status (see `User.STATUS_VALUES`).
"""

from __future__ import annotations

from typing import (
    FrozenSet,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Set,
    Union,
    cast,
    overload,
)

from critic import api
from critic import dbaccess


class Error(api.APIError, object_type="user"):
    """Base exception for all errors related to the User class"""

    pass


class InvalidId(api.InvalidIdError, Error):
    """Raised by `fetch()` when an invalid user id is used."""

    pass


class InvalidIds(api.InvalidIdsError, Error):
    """Raised by `fetchMany()` when invalid user ids are used."""

    pass


class InvalidName(api.InvalidItemError, Error, item_type="name"):
    """Raised by `fetch()` when an invalid user name is used."""

    pass


class InvalidNames(Error, api.InvalidItemsError, items_type="names"):
    """Raised by `fetchMany()` when invalid user names are used."""

    pass


class InvalidRole(Error):
    """Raised when an invalid role is used"""

    def __init__(self, role: str) -> None:
        """Constructor"""
        super(InvalidRole, self).__init__("Invalid role: %r" % role)
        self.role = role


Type = Literal["regular", "anonymous", "system"]
TYPE_VALUES: FrozenSet[Type] = frozenset(["regular", "anonymous", "system"])
"""User type values.

- `"regular"` A regular (human or bot) user.
- `"anonymous"` The anonymous user.
- `"system"` The system."""


def as_type(value: str) -> Type:
    if value not in TYPE_VALUES:
        raise ValueError(f"invalid user type: {value!r}")
    return cast(Type, value)


Status = Literal["current", "absent", "retired", "disabled"]
STATUS_VALUES: FrozenSet[Status] = frozenset(
    ["current", "absent", "retired", "disabled"]
)
"""User status values.

- `"current"` Normal user status.
- `"absent"` On vacation or similar. Not expected to respond quickly.
- `"retired"` No longer active in this system.
- `"disabled"` Deleted user entry."""


def as_status(value: str) -> Status:
    if value not in STATUS_VALUES:
        raise ValueError(f"invalid user status: {value!r}")
    return cast(Status, value)


PasswordStatus = Literal["set", "not-set", "disabled"]
PASSWORD_STATUS_VALUES: FrozenSet[PasswordStatus] = frozenset(
    {"set", "not-set", "disabled"}
)
"""Password status values.

- `"set"` A password is set and can be used to authenticate.
- `"not-set"` No password has been set, but one could be set and then used
    to authenticate.
- `"disabled"` Password authentification has been disabled."""


def as_password_status(value: str) -> PasswordStatus:
    if value not in PASSWORD_STATUS_VALUES:
        raise ValueError(f"invalid user password status: {value!r}")
    return cast(PasswordStatus, value)


class User(api.APIObject):
    """Representation of a Critic user"""

    def __str__(self) -> str:
        if self.is_anonymous:
            return "<anonymous>"
        if self.is_system:
            return "<system>"
        fullname = self.fullname if self.fullname else self.name
        assert fullname
        # if self.email:
        #     return f"{fullname} <{self.email}>"
        return fullname

    def __repr__(self) -> str:
        if self.is_anonymous:
            return "User(anonymous)"
        if self.is_system:
            return "User(system)"
        return f"User(id={self.id}, name={self.name})"

    def __adapt__(self) -> dbaccess.SQLValue:
        return self.id

    @property
    def type(self) -> Type:
        """The type of user: "regular", "anonymous" or "system"."""
        return self._impl.type

    @property
    def id(self) -> Optional[int]:
        """The user's unique id"""
        return self._impl.id

    @property
    def name(self) -> Optional[str]:
        """The user's unique username"""
        return self._impl.name

    @property
    def fullname(self) -> Optional[str]:
        """The user's full name"""
        return self._impl.fullname

    @property
    def status(self) -> Status:
        """The user's status

           For regular users, the value is one of the strings in the
           User.STATUS_VALUES set.

           For the anonymous user, the value is "anonymous".
           For the Critic system user, the value is "system"."""
        return self._impl.status

    @property
    def is_regular(self) -> bool:
        """True if this object represents an anonymous user"""
        return self.type == "regular"

    @property
    def is_anonymous(self) -> bool:
        """True if this object represents an anonymous user"""
        return self.type == "anonymous"

    @property
    def is_system(self) -> bool:
        """True if this object represents an anonymous user"""
        return self.type == "system"

    @property
    async def email(self) -> Optional[str]:
        """The user's selected primary email address

           If the user has no primary email address or if the selected primary
           email address is unverified, this attribute's value is None."""
        useremail = await api.useremail.fetch(self.critic, user=self)
        assert useremail is None or useremail.status != "unverified"
        return useremail.address if useremail else None

    @property
    async def git_emails(self) -> Set[str]:
        """The user's "git" email addresses

           The value is a set of strings.

           These addresses are used to identify the user as author or committer
           of Git commits by matching the email address in the commit's meta
           data."""
        return await self._impl.getGitEmails(self.critic)

    @property
    async def repository_filters(
        self,
    ) -> Mapping[
        api.repository.Repository, List[api.repositoryfilter.RepositoryFilter]
    ]:
        """The user's repository filters

           The value is a dictionary mapping api.repository.Repository objects
           to lists of api.repositoryfilter.RepositoryFilter objects."""
        return await self._impl.getRepositoryFilters(self.critic)

    @property
    def roles(self) -> FrozenSet[str]:
        return self._impl.roles

    def hasRole(self, role: str) -> bool:
        """Return True if the user has the named role

           If the argument is not a valid role name, an InvalidRole exception is
           raised."""
        return self._impl.hasRole(role)

    # async def getPreference(
    #     self, item: str, *, repository: api.repository.Repository = None
    # ) -> api.preference.Preference:
    #     """Fetch the user's preference setting for `item`

    #     The setting is returned as an api.preference.Preference object, whose
    #     'user' and 'repository' attributes can be used to determine whether
    #     there was a per-user and/or per-repository override, or if a system
    #     default value was used.

    #     If 'repository' is not None, fetch a per-repository override if there
    #     is one.

    #     Args:
    #         item (str): The preference item name.
    #         repository (critic.api.repository.Repository): Return the override
    #             for the specified repository, if there is one.

    #     Returns:
    #         A `critic.api.preference.Preference` object.

    #     Raises:
    #         InvalidPreferenceItem: The requested `item` is not valid."""
    #     assert repository is None or isinstance(repository, api.repository.Repository)
    #     return await self._impl.getPreference(self, item, repository)

    async def isAuthorOf(self, commit: api.commit.Commit) -> bool:
        """Return true if this user is the author of the given commit.

        The user's set of declared "git email addresses", as returned by
        `User.git_emails`, is used to make the assessment, which is always an
        approximation.

        Args:
            commit (critic.api.commit.Commit): The Git commit.

        Returns:
            Boolean."""
        return commit.author.email in await self.git_emails

    @property
    async def url_prefixes(self) -> List[str]:
        """URL prefixes the user wishes to see

        A URL prefix will typically be on the format

            <scheme>://<host>[:<port>]

        and thus meant to be prepended to a slash-prefixed path to form a full
        URL to a page.

        On systems that are reachable via e.g. different hostnames, users can
        typically select which URLs they wish to see in e.g. Git hook output."""
        return await self._impl.getURLPrefixes(self)

    @property
    def password_status(self) -> PasswordStatus:
        """The user's password status

           The password status will be one of the strings in the set
           User.PASSWORD_STATUS_VALUES:

             "set": The user has a password set.
             "not-set": The user has no password set, but could set one provided
                        they have some other means of authenticating.
             "disabled": The user has no password, and can not set one, either
                         because the user is not current, or because password
                         authentication is disabled, or not handled by Critic.

           This value should be used by a account UI to determine what kind of
           password update UI to display.

           Note: The user's password is of course not accessible."""
        return self._impl.password_status


@overload
async def fetch(critic: api.critic.Critic, user_id: int, /) -> User:
    ...


@overload
async def fetch(critic: api.critic.Critic, /, *, name: str) -> User:
    ...


async def fetch(
    critic: api.critic.Critic, user_id: int = None, /, *, name: str = None
) -> User:
    """Fetch a User object by user id or name.

    Exactly one of the `user_id` and `name` arguments can be used (i.e. be not
    None.)

    Args:
        critic (critic.api.critic.Critic): The current session.
        user_id: Numeric id of user to fetch.
        name: Name of user to fetch.

    Returns:
        A `User` object.

    Raises:
        InvalidUserId: The `user_id` is not a valid user id.
        InvalidUserName: The `name` is not a valid user name."""
    from .impl import user as _impl

    return await _impl.fetch(critic, user_id, name)


@overload
async def fetchMany(
    critic: api.critic.Critic, user_ids: Iterable[int], /
) -> Sequence[User]:
    ...


@overload
async def fetchMany(
    critic: api.critic.Critic, /, *, names: Iterable[str]
) -> Sequence[User]:
    ...


async def fetchMany(
    critic: api.critic.Critic,
    user_ids: Iterable[int] = None,
    /,
    *,
    names: Iterable[str] = None,
) -> Sequence[User]:
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
    from .impl import user as _impl

    return await _impl.fetchMany(critic, user_ids, names)


async def fetchAll(
    critic: api.critic.Critic, /, *, status: Union[Status, Iterable[Status]] = None,
) -> Sequence[User]:
    """Fetch User objects for all users of the system

       If |status| is not None, it must be one of the user statuses "current",
       "absent", "retired" or "disabled", or an iterable containing one or more
       of those strings."""
    from .impl import user as _impl

    statuses: Optional[Set[Status]]
    if status is not None:
        if isinstance(status, str):
            statuses = {status}
        else:
            statuses = set(status)
    else:
        statuses = None
    return await _impl.fetchAll(critic, statuses)


def anonymous(critic: api.critic.Critic) -> User:
    """Fetch a User object representing the anonymous user.

    Args:
        critic (critic.api.critic.Critic): The current session.

    Returns:
        An `User` object whose `User.is_anonymous` is `True`."""
    from .impl import user as _impl

    return _impl.anonymous(critic)


def system(critic: api.critic.Critic) -> User:
    """Fetch a User object representing the system"""
    from .impl import user as _impl

    return _impl.system(critic)


resource_name = table_name = "users"
