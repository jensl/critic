# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2016 the Critic contributors, Opera Software ASA
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

import auth

class Session(object):
    def __init__(self, user, session_type):
        self.user = user
        self.session_type = session_type

class SessionError(jsonapi.Error):
    http_status = 403
    title = "Session error"

@jsonapi.PrimaryResource
class Sessions(object):
    """The session of the accessing client."""

    name = "sessions"
    value_class = Session

    anonymous_create = True

    @staticmethod
    def json(value, parameters):
        """Session {
             "user": integer, // the signed in user's id, or null
             "type": "normal" or "accesstoken", or null,
             "fields": [
                 {
                     "identifier": string, // unique field identifier
                     "label": string,      // UI label
                     "hidden": boolean,    // true for passwords
                     "description": string or null
                 },
                 ...
             ]
           }"""

        fields = []

        for db_field in auth.DATABASE.getFields():
            hidden, identifier, label = db_field[:3]
            if len(db_field) == 4:
                description = db_field[3]
            else:
                description = None
            fields.append({
                "identifier": identifier,
                "label": label,
                "hidden": hidden,
                "description": description
            })

        return parameters.filtered(
            "sessions", { "user": value.user,
                          "type": value.session_type,
                          "fields": fields })

    @staticmethod
    def single(parameters, argument):
        """Retrieve the current session.

           CURRENT : "current"

           Retrieve the current session."""

        if argument != "current":
            raise jsonapi.UsageError('Resource argument must be "current"')

        user = parameters.critic.actual_user
        if parameters.critic.access_token:
            session_type = "accesstoken"
        elif user:
            session_type = "normal"
        else:
            session_type = None
        return Session(user, session_type)

    @staticmethod
    def create(parameters, value, values, data):
        fields = auth.DATABASE.getFields()

        converted = jsonapi.convert(parameters, {
            fieldname: str
            for hidden, fieldname, label in fields
        }, data)

        critic = parameters.critic

        try:
            auth.DATABASE.authenticate(critic.database, converted)
        except auth.AuthenticationFailed as error:
            raise SessionError(error.message)
        except auth.WrongPassword:
            raise SessionError("Wrong password")

        auth.createSessionId(
            critic.database, parameters.req, critic.database.user)

        return Session(critic.actual_user, "normal"), None

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic

        auth.deleteSessionId(
            critic.database, parameters.req, critic.database.user)
