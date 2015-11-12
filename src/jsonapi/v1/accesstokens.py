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
import jsonapi

ACCESS_TYPE = frozenset(["user", "anonymous", "system"])

from accesscontrolprofiles import (RULE, CATEGORIES, HTTP_EXCEPTION,
                                   REPOSITORIES_EXCEPTION, EXTENSION_EXCEPTION,
                                   PROFILE, updateProfile)

def modifyAccessToken(transaction, access_token):
    if access_token.user:
        return transaction \
            .modifyUser(access_token.user) \
            .modifyAccessToken(access_token)
    return transaction \
        .modifyAccessToken(access_token)

@jsonapi.PrimaryResource
class AccessTokens(object):
    """Access tokens."""

    name = "accesstokens"
    contexts = (None, "users")
    value_class = api.accesstoken.AccessToken
    exceptions = (api.accesstoken.AccessTokenError,)
    objects = ("profile",
               "profile/http",
               "profile/repositories",
               "profile/extensions")
    lists = ("profile/http/exceptions",
             "profile/repositories/exceptions",
             "profile/extensions/exceptions")

    @staticmethod
    def json(value, parameters):
        """AccessToken {
             "id": integer,
             "access_type": "user", "anonymous" or "system",
             "user": integer or null,
             "part1": string,
             "part2": string,
             "title": string or null,
             "profile": null or AccessControlProfile
           }

           AccessControlProfile {
             "http": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "request_method": string or null,
                 "path_pattern": string or null
               }]
             },
             "repositories": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "access_type": "read" or "modify",
                 "repository": integer
               }]
             },
             "extensions": {
               "rule": "allow" or "deny",
               "exceptions: [{
                 "id": integer,
                 "access_type": "install" or "execute",
                 "extension": string,
               }]
             }
           }"""

        # Make sure that only administrator users can access other user's access
        # tokens or access tokens that do not belong to any user.
        if value.access_type != "user" \
                or parameters.critic.actual_user != value.user:
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        data = { "id": value.id,
                 "access_type": value.access_type,
                 "user": value.user,
                 "part1": value.part1,
                 "part2": value.part2,
                 "title": value.title }

        if value.profile:
            data["profile"] = {
                "http": {
                    "rule": value.profile.http.rule,
                    "exceptions": [{
                        "id": exception.id,
                        "request_method": exception.request_method,
                        "path_pattern": exception.path_pattern
                    } for exception in value.profile.http.exceptions]
                },
                "repositories": {
                    "rule": value.profile.repositories.rule,
                    "exceptions": [{
                        "id": exception.id,
                        "access_type": exception.access_type,
                        "repository": exception.repository
                    } for exception in value.profile.repositories.exceptions]
                },
                "extensions": {
                    "rule": value.profile.extensions.rule,
                    "exceptions": [{
                        "id": exception.id,
                        "access_type": exception.access_type,
                        "extension": exception.extension
                    } for exception in value.profile.extensions.exceptions]
                },
            }
        else:
            data["profile"] = None

        return parameters.filtered("accesstokens", data)

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) access tokens.

           TOKEN_ID : integer

           Retrieve an access token identified by its unique numeric id."""

        value = api.accesstoken.fetch(parameters.critic,
                                      jsonapi.numeric_id(argument))

        if "users" in parameters.context:
            if value.user != parameters.context["users"]:
                raise InvalidAccessTokenId(jsonapi.numeric_id(argument))

        return value

    @staticmethod
    def multiple(parameters):
        """All access tokens."""

        user = jsonapi.deduce("v1/users", parameters)

        # Only administrators are allowed to access all access tokens in the
        # system.
        if user is None:
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        return api.accesstoken.fetchAll(parameters.critic, user=user)

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)
        access_tokens = [value] if value else values
        path = parameters.subresource_path

        if 0 < len(path) < 3:
            raise jsonapi.UsageError("Invalid POST request")

        if len(path) == 3 \
                and path[0] == "profile" \
                and path[1] in CATEGORIES \
                and path[2] == "exceptions":
            # Create an rule exception.

            if path[1] == "http":
                exception_type = HTTP_EXCEPTION
            elif path[1] == "repositories":
                exception_type = REPOSITORIES_EXCEPTION
            else:
                exception_type = EXTENSION_EXCEPTION

            converted = jsonapi.convert(
                parameters,
                exception_type,
                data)

            with api.transaction.Transaction(critic) as transaction:
                for access_token in access_tokens:
                    modifier = modifyAccessToken(transaction, access_token) \
                        .modifyProfile() \
                        .modifyExceptions(path[1]) \
                        .add(**converted)

            return value, values

        # Create an access token.
        assert not access_tokens

        converted = jsonapi.convert(
            parameters,
            { "access_type?": ACCESS_TYPE,
              "title?": str,
              "profile?": PROFILE },
            data)

        result = []

        def collectAccessToken(token):
            assert isinstance(token, api.accesstoken.AccessToken)
            result.append(token)

        with api.transaction.Transaction(critic) as transaction:
            modifier = transaction \
                .modifyUser(user)

            access_type = converted.get("access_type", "user")

            access_token = modifier.createAccessToken(
                access_type=access_type,
                title=converted.get("title"),
                callback=collectAccessToken)

            if "profile" in converted:
                modifier = transaction
                if access_type == "user":
                    modifier = modifier.modifyUser(user)
                modifier = modifier \
                     .modifyAccessToken(access_token) \
                     .modifyProfile()
                updateProfile(modifier, converted["profile"])

        assert len(result) == 1
        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic

        if value:
            access_tokens = [value]
        else:
            access_tokens = values

        path = parameters.subresource_path

        if path == ["profile"]:
            converted = jsonapi.convert(parameters, PROFILE, data)

            with api.transaction.Transaction(critic) as transaction:
                for access_token in access_tokens:
                    modifier = modifyAccessToken(transaction, access_token) \
                        .modifyProfile()

                    updateProfile(modifier, converted)

            return

        if len(path) == 2 \
                and path[0] == "profile" \
                and path[1] in CATEGORIES:
            if path[1] == "http":
                exception_type = HTTP_EXCEPTION
            elif path[1] == "repositories":
                exception_type = REPOSITORIES_EXCEPTION
            else:
                exception_type = EXTENSION_EXCEPTION

            converted = jsonapi.convert(
                parameters,
                {
                    "rule?": RULE,
                    "exceptions?": [exception_type]
                },
                data)

            with api.transaction.Transaction(critic) as transaction:
                for access_token in access_tokens:
                    modifier = modifyAccessToken(transaction, access_token) \
                        .modifyProfile()

                    updateProfile(modifier, { path[1]: converted })

            return

        converted = jsonapi.check.convert(
            parameters,
            {
                "title?": str,
                "profile?": PROFILE,
            },
            data)

        with api.transaction.Transaction(critic) as transaction:
            for access_token in access_tokens:
                modifier = modifyAccessToken(transaction, access_token)

                if "title" in converted:
                    modifier.setTitle(converted["title"])

                if "profile" in converted:
                    updateProfile(modifier.modifyProfile(),
                                  converted["profile"])

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            access_tokens = [value]
        else:
            access_tokens = values

        if 3 <= len(path) <= 4 \
                and path[0] == "profile" \
                and path[1] in CATEGORIES \
                and path[2] == "exceptions":
            exception_id = None
            if len(path) == 4:
                exception_id = path[3]

            with api.transaction.Transaction(critic) as transaction:
                for access_token in access_tokens:
                    modifier = modifyAccessToken(transaction, access_token) \
                        .modifyProfile() \
                        .modifyExceptions(path[1])

                    if exception_id is None:
                        modifier.deleteAll()
                    else:
                        modifier.delete(exception_id)

            return value, values

        if path:
            raise jsonapi.UsageError("Invalid DELETE request")

        with api.transaction.Transaction(critic) as transaction:
            for access_token in access_tokens:
                modifyAccessToken(transaction, access_token) \
                    .delete()
