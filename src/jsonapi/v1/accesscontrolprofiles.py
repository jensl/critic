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

RULE = api.accesscontrolprofile.AccessControlProfile.RULE_VALUES
CATEGORIES = frozenset(["http", "repositories", "extensions"])
REQUEST_METHOD = api.accesscontrolprofile \
        .AccessControlProfile.HTTPException.REQUEST_METHODS
REPOSITORY_ACCESS_TYPE = api.accesscontrolprofile \
        .AccessControlProfile.RepositoryException.ACCESS_TYPES
EXTENSION_ACCESS_TYPE = api.accesscontrolprofile \
        .AccessControlProfile.ExtensionException.ACCESS_TYPES

HTTP_EXCEPTION = {
    "request_method=null": REQUEST_METHOD,
    "path_pattern=null": jsonapi.check.RegularExpression
}
REPOSITORIES_EXCEPTION = {
    "access_type=null": REPOSITORY_ACCESS_TYPE,
    "repository=null": api.repository.Repository
}
EXTENSION_EXCEPTION = {
    "access_type=null": EXTENSION_ACCESS_TYPE,
    "extension=null": api.extension.Extension
}

PROFILE = {
    "http?": {
        "rule": RULE,
        "exceptions?": [HTTP_EXCEPTION]
    },
    "repositories?": {
        "rule": RULE,
        "exceptions?": [REPOSITORIES_EXCEPTION]
    },
    "extensions?": {
        "rule": RULE,
        "exceptions?": [EXTENSION_EXCEPTION]
    }
}

PROFILE_WITH_TITLE = PROFILE.copy()
PROFILE_WITH_TITLE["title?"] = str

def updateProfile(profile_modifier, converted):
    def updateExceptions(exceptions_modifier, exceptions):
        exceptions_modifier.deleteAll()
        for exception in exceptions:
            exceptions_modifier.add(**exception)

    def updateCategory(category):
        if category not in converted:
            return
        if "rule" in converted[category]:
            profile_modifier.setRule(category, converted[category]["rule"])
        if "exceptions" in converted[category]:
            updateExceptions(profile_modifier.modifyExceptions(category),
                             converted[category]["exceptions"])

    if "title" in converted:
        profile_modifier.setTitle(converted["title"])

    updateCategory("http")
    updateCategory("repositories")
    updateCategory("extensions")

@jsonapi.PrimaryResource
class AccessControlProfiles(object):
    """The access control profiles of this system."""

    name = "accesscontrolprofiles"
    value_class = api.accesscontrolprofile.AccessControlProfile
    exceptions = (api.accesscontrolprofile.AccessControlProfileError,)
    objects = ("http",
               "repositories",
               "extensions")
    lists = ("http/exceptions",
             "repositories/exceptions",
             "extensions/exceptions")

    @staticmethod
    def json(value, parameters, linked):
        """AccessControlProfile {
             "id": integer,
             "title": string or null,
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

        # Make sure that only administrator users can access profiles that are
        # not connected to access tokens, and that only administrator users and
        # the user that owns the access token can access other profiles.
        if not value.access_token \
                or value.access_token.access_type != "user" \
                or parameters.critic.actual_user != value.access_token.user:
            api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        for exception in value.repositories.exceptions:
            if exception.repository:
                linked.add("v1/repositories", exception.repository)
        for exception in value.extensions.exceptions:
            if exception.extension:
                linked.add("v1/extensions", exception.extension)

        return parameters.filtered("accesscontrolprofiles", {
            "id": value.id,
            "title": value.title,
            "http": {
                "rule": value.http.rule,
                "exceptions": [{
                    "id": exception.id,
                    "request_method": exception.request_method,
                    "path_pattern": exception.path_pattern
                } for exception in value.http.exceptions]
            },
            "repositories": {
                "rule": value.repositories.rule,
                "exceptions": [{
                    "id": exception.id,
                    "access_type": exception.access_type,
                    "repository": (exception.repository.id
                                   if exception.repository else None)
                } for exception in value.repositories.exceptions]
            },
            "extensions": {
                "rule": value.extensions.rule,
                "exceptions": [{
                    "id": exception.id,
                    "access_type": exception.access_type,
                    "extension": (exception.extension.id
                                  if exception.extension else None)
                } for exception in value.extensions.exceptions]
            },
        })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) access control profiles.

           PROFILE_ID : integer

           Retrieve an access control profile identified by the profile's unique
           numeric id."""

        return api.accesscontrolprofile.fetch(
            parameters.critic, profile_id=jsonapi.numeric_id(argument))

    @staticmethod
    def multiple(parameters):
        """Retrieve all primary access control profiles in the system.

           title : TITLE : string

           Retrieve only access control profiles with a matching title."""
        title_parameter = parameters.getQueryParameter("title")
        return api.accesscontrolprofile.fetchAll(
            parameters.critic, title=title_parameter)

    @staticmethod
    def deduce(parameters):
        profile = parameters.context.get("accesscontrolprofiles")
        profile_parameter = parameters.getQueryParameter("profile")
        if profile_parameter is not None:
            if profile is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: profile=%s" % profile_parameter)
            profile_id = jsonapi.numeric_id(profile_parameter)
            profile = api.accesscontrolprofile.fetch(
                parameters.critic, profile_id=profile_id)
        return profile

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)
        profiles = [value] if value else values
        path = parameters.subresource_path

        if 0 < len(path) < 2:
            raise jsonapi.UsageError("Invalid POST request")

        if len(path) == 2 \
                and path[0] in CATEGORIES \
                and path[1] == "exceptions":
            # Create an rule exception.

            if path[0] == "http":
                exception_type = HTTP_EXCEPTION
            elif path[0] == "repositories":
                exception_type = REPOSITORIES_EXCEPTION
            else:
                exception_type = EXTENSION_EXCEPTION

            converted = jsonapi.convert(
                parameters,
                exception_type,
                data)

            with api.transaction.Transaction(critic) as transaction:
                for profile in profiles:
                    modifier = transaction.modifyAccessControlProfile(profile) \
                        .modifyExceptions(path[0]) \
                        .add(**converted)

            return value, values

        # Create an access control profile.
        assert not profiles

        converted = jsonapi.convert(parameters, PROFILE_WITH_TITLE, data)

        result = []

        def collectAccessControlProfile(profile):
            assert isinstance(
                profile, api.accesscontrolprofile.AccessControlProfile)
            result.append(profile)

        with api.transaction.Transaction(critic) as transaction:
            modifier = transaction.createAccessControlProfile(
                callback=collectAccessControlProfile)
            updateProfile(modifier, converted)

        assert len(result) == 1
        return result[0], None

    @staticmethod
    def update(parameters, value, values, data):
        critic = parameters.critic

        if value:
            profiles = [value]
        else:
            profiles = values

        path = parameters.subresource_path

        if len(path) == 1 and path[0] in CATEGORIES:
            if path[0] == "http":
                exception_type = HTTP_EXCEPTION
            elif path[0] == "repositories":
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
                for profile in profiles:
                    modifier = transaction.modifyAccessControlProfile(profile)
                    updateProfile(modifier, { path[0]: converted })

            return

        converted = jsonapi.convert(parameters, PROFILE_WITH_TITLE, data)

        with api.transaction.Transaction(critic) as transaction:
            for profile in profiles:
                modifier = transaction.modifyAccessControlProfile(profile)
                updateProfile(modifier, converted)

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic
        path = parameters.subresource_path

        if value:
            profiles = [value]
        else:
            profiles = values

        if len(path) in (2, 3) \
                and path[0] in CATEGORIES \
                and path[1] == "exceptions":
            exception_id = path[2] if len(path) == 3 else None

            with api.transaction.Transaction(critic) as transaction:
                for profile in profiles:
                    modifier = transaction.modifyAccessControlProfile(profile) \
                        .modifyProfile() \
                        .modifyExceptions(path[0])

                    if exception_id is None:
                        modifier.deleteAll()
                    else:
                        modifier.delete(exception_id)

            return value, values

        if path:
            raise jsonapi.UsageError("Invalid DELETE request")

        with api.transaction.Transaction(critic) as transaction:
            for profile in profiles:
                transaction.modifyAccessControlProfile(profile) \
                    .delete()
