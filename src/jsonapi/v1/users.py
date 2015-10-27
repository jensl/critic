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

           USER_ID : integer or "me"

           Retrieve a user identified by the user's unique numeric id, or the
           identifier "me" to retrieve the current user."""

        if argument == "me":
            user = parameters.critic.actual_user
            if user is None:
                raise api.user.UserError("'users/me' (not signed in)")
        else:
            user = api.user.fetch(parameters.critic,
                                  user_id=jsonapi.numeric_id(argument))
        return Users.setAsContext(parameters, user)

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
    def update(parameters, value, values, data):
        if values and len(values) != 1:
            raise UsageError("Updating multiple users not supported")

        critic = parameters.critic

        if values:
            value = values[0]

        converted = jsonapi.convert(parameters, { "fullname?": str }, data)

        with api.transaction.Transaction(critic) as transaction:
            if "fullname" in converted:
                new_fullname = converted["fullname"].strip()
                if not new_fullname:
                    raise jsonapi.InputError("Empty new fullname")
                transaction.modifyUser(value).setFullname(new_fullname)

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
    def single(parameters, argument):
        """A primary email address by index.

           INDEX : integer

           Retrieve a primary email address identified by its index."""

        emails = list(parameters.context["users"].primary_emails)

        try:
            return emails[jsonapi.numeric_id(argument) - 1]
        except IndexError:
            raise jsonapi.PathError("List index out of range")

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
    exceptions = (api.repository.RepositoryError, KeyError)

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
    def single(parameters, argument):
        """Retrieve one (or more) of a user's repository filters.

           FILTER_ID : integer

           Retrieve a filter identified by the filters's unique numeric id."""

        user = parameters.context["users"]
        filter_id = jsonapi.numeric_id(argument)

        for repository_filters in user.repository_filters.values():
            for repository_filter in repository_filters:
                if repository_filter.id == filter_id:
                    return repository_filter

        raise KeyError("invalid filter id: %d" % filter_id)

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
        return jsonapi.sorted_by_id(repository_filters)

    @staticmethod
    def create(parameters, value, values, data):
        import reviewing.filters

        class FilterPath(jsonapi.check.StringChecker):
            def check(self, context, value):
                path = reviewing.filters.sanitizePath(value)
                try:
                    reviewing.filters.validatePattern(path)
                except reviewing.filters.PatternError as error:
                    return error.message

            def convert(self, context, value):
                return reviewing.filters.sanitizePath(value)

        critic = parameters.critic
        subject = parameters.context["users"]

        if parameters.subresource_path:
            if value:
                repository_filters = [value]
            else:
                repository_filters = values

            assert parameters.subresource_path[0] == "delegates"
            assert len(parameters.subresource_path) == 1

            converted = jsonapi.convert(parameters, api.user.User, data)

            with api.transaction.Transaction(critic) as transaction:
                for repository_filter in repository_filters:
                    delegates = set(repository_filter.delegates)

                    if converted not in delegates:
                        delegates.add(converted)
                        transaction \
                            .modifyUser(subject) \
                            .modifyFilter(repository_filter) \
                            .setDelegates(delegates)

            return value, values

        converted = jsonapi.convert(
            parameters,
            { "type": set(("reviewer", "watcher", "ignore")),
              "path": FilterPath,
              "repository": api.repository.Repository,
              "delegates?": [api.user.User] },
            data)

        result = []

        with api.transaction.Transaction(critic, result) as transaction:
            transaction.modifyUser(subject).createFilter(
                filter_type=converted["type"],
                repository=converted["repository"],
                path=converted["path"],
                delegates=converted.get("delegates", []))

        assert len(result) == 1
        assert isinstance(result[0], api.filters.RepositoryFilter)

        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic

        if parameters.subresource_path:
            assert parameters.subresource_path[0] == "delegates"

            if len(parameters.subresource_path) == 2:
                raise jsonapi.UsageError("can't update specific delegate")

            delegates = jsonapi.convert(
                parameters, [api.user.User], data)
        else:
            converted = jsonapi.convert(
                parameters,
                { "delegates?": [api.user.User] },
                data)

            delegates = converted.get("delegates")

        if value:
            repository_filters = [value]
        else:
            repository_filters = values

        with api.transaction.Transaction(critic) as transaction:
            for repository_filter in repository_filters:
                if delegates is not None:
                    transaction \
                        .modifyUser(repository_filter.subject) \
                        .modifyFilter(repository_filter) \
                        .setDelegates(delegates)

        return value, values

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic

        if parameters.subresource_path:
            assert value and not values
            assert parameters.subresource_path[0] == "delegates"

            repository_filter = value
            delegates = jsonapi.sorted_by_id(repository_filter.delegates)

            if len(parameters.subresource_path) == 1:
                # Delete all delegates.
                delegates = []
            else:
                del delegates[parameters.subresource_path[1] - 1]

            with api.transaction.Transaction(critic) as transaction:
                transaction \
                    .modifyUser(repository_filter.subject) \
                    .modifyFilter(repository_filter) \
                    .setDelegates(delegates)

            # Remove the last component from the sub-resource path, since we've
            # just deleted the specified sub-resource(s).
            del parameters.subresource_path[-1]

            return value, values

        if value:
            repository_filters = [value]
        else:
            repository_filters = values

        with api.transaction.Transaction(critic) as transaction:
            for repository_filter in repository_filters:
                transaction \
                    .modifyUser(repository_filter.subject) \
                    .modifyFilter(repository_filter) \
                    .delete()
