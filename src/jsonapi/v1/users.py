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

import itertools

import api
import jsonapi

def from_argument(parameters, argument):
    user_id, name = jsonapi.id_or_name(argument)
    return api.user.fetch(
        parameters.critic, user_id=user_id, name=name)

@jsonapi.PrimaryResource
class Users(object):
    """The users of this system."""

    name = "users"
    value_class = api.user.User
    exceptions = (api.user.UserError,)

    @staticmethod
    def json(value, parameters):
        """User {
             "id": integer, // the user's id
             "name": string, // the user's unique user name
             "fullname": string, // the user's full name
             "status": string, // the user's status: "current", "absent" or "retired"
             "email": string, // the user's primary email address
           }"""

        return parameters.filtered(
            "users", { "id": value.id,
                       "name": value.name,
                       "fullname": value.fullname,
                       "status": value.status,
                       "email": value.email })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) users of this system.

           USER_ID : integer

           Retrieve a user identified by the user's unique numeric id."""

        return Users.setAsContext(parameters, api.user.fetch(
            parameters.critic, user_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(parameters):
        """Retrieve a single named user or all users of this system.

           name : NAME : string

           Retrieve only the user with the given name.  This is equivalent to
           accessing /api/v1/users/USER_ID with that user's numeric id.  When
           used, any other parameters are ignored.

           status : USER_STATUS[,USER_STATUS,...] : string

           Include only users whose status is one of the specified.  Valid
           values are: <code>current</code>, <code>absent</code>,
           <code>retired</code>.

           sort : SORT_KEY : string

           Sort the returned users by the specified key.  Valid values are:
           <code>id</code>, <code>name</code>, <code>fullname</code>,
           <code>email</code>."""

        name_parameter = parameters.getQueryParameter("name")
        if name_parameter:
            return api.user.fetch(parameters.critic, name=name_parameter)
        status_parameter = parameters.getQueryParameter("status")
        if status_parameter:
            status = set(status_parameter.split(","))
            invalid = status - api.user.User.STATUS_VALUES
            if invalid:
                raise jsonapi.UsageError(
                    "Invalid user status values: %s"
                    % ", ".join(map(repr, sorted(invalid))))
        else:
            status = None
        sort_parameter = parameters.getQueryParameter("sort")
        if sort_parameter:
            if sort_parameter not in ("id", "name", "fullname", "email"):
                raise jsonapi.UsageError("Invalid user sort parameter: %r"
                                         % sort_parameter)
            sort_key = lambda user: getattr(user, sort_parameter)
        else:
            sort_key = lambda user: user.id
        return sorted(api.user.fetchAll(parameters.critic, status=status),
                      key=sort_key)

    @staticmethod
    def deduce(parameters):
        user = parameters.context.get("users")
        user_parameter = parameters.getQueryParameter("user")
        if user_parameter is not None:
            if user is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: user=%s"
                    % user_parameter)
            user = from_argument(parameters, user_parameter)
        return user

    @staticmethod
    def setAsContext(parameters, user):
        parameters.setContext(Users.name, user)
        return user

@jsonapi.PrimaryResource
class Emails(object):
    """A user's primary email addresses.

       A "primary" email address is one that Critic would send emails to.  A
       user can have multiple primary email addresses registered, but at most
       one of them can be selected.  Emails are only sent to a selected primary
       email address.

       A user also has a set of "Git" email addresses.  Those are only compared
       against Git commit meta-data, and are never used when sending emails."""

    name = "emails"
    contexts = ("users",)
    value_class = api.user.User.PrimaryEmail

    @staticmethod
    def json(value, parameters):
        """Email {
             "address": string, // the email address
             "selected": string, // true if address is selected
             "verified": string, // true if address is verified
           }"""

        return parameters.filtered(
            "emails", { "address": value.address,
                        "selected": value.selected,
                        "verified": value.verified })

    @staticmethod
    def multiple(parameters):
        """All primary email addresses."""

        return parameters.context["users"].primary_emails

@jsonapi.PrimaryResource
class Filters(object):
    """A user's repository filters."""

    name = "filters"
    contexts = ("users",)
    value_class = api.filters.RepositoryFilter
    exceptions = (api.repository.RepositoryError,)

    lists = frozenset(("delegates",))

    @staticmethod
    def json(value, parameters):
        """Filter {
             "id": integer, // the filter's id
             "type": string, // "reviewer", "watcher" or "ignored"
             "path": string, // the filtered path
             "repository": integer, // the filter's repository's id
             "delegates": integer[], // list of user ids
           }"""

        return parameters.filtered("filters", {
            "id": value.id,
            "type": value.type,
            "path": value.path,
            "repository": value.repository,
            "delegates": jsonapi.sorted_by_id(value.delegates)
        })

    @staticmethod
    def multiple(parameters):
        """All repository filters.

           repository : REPOSITORY : -

           Include only filters for the specified repository, identified by its
           unique numeric id or short-name."""

        user = parameters.context["users"]
        repository_parameter = parameters.getQueryParameter("repository")
        if repository_parameter:
            repository_id = name = None
            try:
                repository_id = int(repository_parameter)
            except ValueError:
                name = repository_parameter
            repository = api.repository.fetch(
                parameters.critic, repository_id=repository_id, name=name)
            repository_filters = user.repository_filters.get(
                repository, [])
        else:
            repository_filters = itertools.chain(
                *user.repository_filters.values())
        return sorted(repository_filters,
                      key=lambda repository_filter: repository_filter.id)
