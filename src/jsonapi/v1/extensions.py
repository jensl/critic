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

@jsonapi.PrimaryResource
class Extensions(object):
    """Extensions."""

    name = "extensions"
    contexts = (None, "users")
    value_class = api.extension.Extension
    exceptions = (api.extension.ExtensionError,)

    @staticmethod
    def json(value, parameters):
        """Extension {
             "id": integer,
             "name": string,
             "key": string,
             "publisher": integer or null,
           }"""

        data = { "id": value.id,
                 "name": value.name,
                 "key": value.key,
                 "publisher": value.publisher }

        return parameters.filtered("extensions", data)

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) extensions by id.

           EXTENSION_ID : integer

           Retrieve an extension identified by its unique numeric id."""

        value = api.extension.fetch(parameters.critic,
                                    jsonapi.numeric_id(argument))

        if "users" in parameters.context:
            if value.publisher != parameters.context["users"]:
                raise InvalidExtensionId(jsonapi.numeric_id(argument))

        return value

    @staticmethod
    def multiple(parameters):
        """Retrieve a single extension by key or all extensions.

           key : KEY : string

           Retrieve only the extension with the given key.  This is equivalent
           to accessing /api/v1/extensions/EXTENSION_ID with that extension's
           numeric id.  When used, other parameters are ignored.

           installed_by : INSTALLED_BY : integer or string

           Retrieve only extensions installed by the specified user.  The user
           can be identified by numeric id or username."""

        key_parameter = parameters.getQueryParameter("key")
        if key_parameter:
            return api.extension.fetch(parameters.critic, key=key_parameter)

        installed_by = jsonapi.from_parameter(
            "v1/users", "installed_by", parameters)

        return api.extension.fetchAll(
            parameters.critic,
            publisher=jsonapi.deduce("v1/users", parameters),
            installed_by=installed_by)
