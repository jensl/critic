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

api_module = api.labeledaccesscontrolprofile

@jsonapi.PrimaryResource
class LabeledAccessControlProfiles(object):
    """The labeled access control profile selectorss of this system."""

    name = "labeledaccesscontrolprofiles"
    contexts = (None, "accesscontrolprofiles")
    value_class = api_module.LabeledAccessControlProfile
    exceptions = api_module.LabeledAccessControlProfileError

    @staticmethod
    def json(value, parameters, linked):
        """LabeledAccessControlProfile {
             "labels": [string],
             "profile": integer
           }"""

        # Make sure that only administrator users can access.
        api.PermissionDenied.raiseUnlessAdministrator(parameters.critic)

        return parameters.filtered("labeledaccesscontrolprofiles", {
            "labels": value.labels,
            "profile": value.profile.id,
        })

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) access control profiles.

           LABELS : string

           Retrieve an access control profile identified by the profile
           selectors's set of labels. Separate labels with pipe ('|')
           characters."""

        return api.accesscontrolprofile.fetch(
            parameters.critic, labels=argument.split("|"))

    @staticmethod
    def multiple(parameters):
        """Retrieve all labeled access control profile selectors in the system.

           profile : PROFILE_ID : integer

           Include only selectors selecting the given profile, identified by its
           unique numeric id."""
        profile = jsonapi.deduce("v1/accesscontrolprofiles", parameters)
        return api.labeledaccesscontrolprofile.fetchAll(
            parameters.critic, profile=profile)

    @staticmethod
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = parameters.context.get("users", critic.actual_user)

        if parameters.subresource_path:
            raise jsonapi.UsageError("Invalid POST request")

        # Create a labeled access control profile selector.
        assert not (value or values)

        converted = jsonapi.convert(parameters, {
            "labels": [str],
            "profile": api.accesscontrolprofile.AccessControlProfile
        }, data)

        result = []

        def collectLabeledAccessControlProfile(labeled_profile):
            assert isinstance(
                labeled_profile,
                api.labeledaccesscontrolprofile.LabeledAccessControlProfile)
            result.append(labeled_profile)

        with api.transaction.Transaction(critic) as transaction:
            transaction.createLabeledAccessControlProfile(
                converted["labels"], converted["profile"],
                callback=collectLabeledAccessControlProfile)

        assert len(result) == 1
        return result[0], None
