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

    @staticmethod
    def json(value, parameters):
        """AccessToken {
             "id": integer,
             "access_type": "user", "anonymous" or "system",
             "user": integer or null,
             "part1": string,
             "part2": string,
             "title": string or null
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

        # Create an access token.
        assert not access_tokens

        converted = jsonapi.check.convert(
            parameters,
            { "access_type?": set(("user", "anonymous", "system")),
              "title?": str },
            data)

        result = []

        def collectAccessToken(token):
            assert isinstance(token, api.accesstoken.AccessToken)
            result.append(token)

        with api.transaction.Transaction(critic) as transaction:
            transaction \
                .modifyUser(user) \
                .createAccessToken(
                    access_type=converted.get("access_type", "user"),
                    title=converted.get("title"),
                    callback=collectAccessToken)

        assert len(result) == 1
        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic

        if value:
            access_tokens = [value]
        else:
            access_tokens = values

        converted = jsonapi.check.convert(
            parameters, { "title": str }, data)

        with api.transaction.Transaction(critic) as transaction:
            for access_token in access_tokens:
                modifyAccessToken(transaction, access_token) \
                    .setTitle(converted["title"])

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic

        if value:
            access_tokens = [value]
        else:
            access_tokens = values

        with api.transaction.Transaction(critic) as transaction:
            for access_token in access_tokens:
                modifyAccessToken(transaction, access_token) \
                    .delete()
