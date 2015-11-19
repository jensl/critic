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

import dbutils
import configuration
import auth

from operation import Operation, OperationResult, Optional, Request
from operation.manipulateuser import sendVerificationMail, checkEmailAddressSyntax

class RegisterUser(Operation):
    def __init__(self):
        super(RegisterUser, self).__init__(
            { "req": Request,
              "username": str,
              "fullname": str,
              "email": str,
              "password": Optional(str),
              "external": Optional({ "provider": set(auth.PROVIDERS.keys()),
                                     "account": str,
                                     "token": str }) },
            accept_anonymous_user=True)

    def process(self, db, user, req, username, fullname, email,
                password=None, external=None):
        cursor = db.cursor()

        if not fullname:
            fullname = username
        if not email:
            email = None
        if not password:
            # Empty password => disabled.
            password = None

        if external:
            provider_config = configuration.auth.PROVIDERS[external["provider"]]
            provider = auth.PROVIDERS[external["provider"]]

        # Check that user registration is actually enabled.  This would also
        # disable the UI for user registration, of course, but the UI could be
        # bypassed, so we should check here as well.
        if not configuration.base.ALLOW_USER_REGISTRATION:
            if not external or not provider_config["allow_user_registration"]:
                return OperationResult(
                    message="User registration is not enabled.")

        # Check that the user name is valid.
        try:
            auth.validateUserName(username)
        except auth.InvalidUserName as error:
            return OperationResult(
                message="<u>Invalid user name</u><br>" + str(error),
                focus="#newusername")

        # Check that the user name is not already taken.
        cursor.execute("SELECT 1 FROM users WHERE name=%s", (username,))
        if cursor.fetchone():
            return OperationResult(
                message="A user named '%s' already exists!" % username,
                focus="#newusername")

        # Check that the email address has some hope of being valid.
        if email and not checkEmailAddressSyntax(email):
            return OperationResult(
                message=("<u>Invalid email address</u><br>"
                         "Please provide an address on the form user@host!"),
                focus="#email")

        # Check that we have either a password or an external authentication
        # provider.  If we have neither, the user wouldn't be able to sign in.
        if password is None and external is None:
            return OperationResult(
                message="Empty password.",
                focus="#password1")

        if password:
            password = auth.hashPassword(password)

        verify_email_address = configuration.base.VERIFY_EMAIL_ADDRESSES

        if external:
            # Check that the external authentication token is valid.
            if not provider.validateToken(db, external["account"],
                                          external["token"]):
                return OperationResult(
                    message="Invalid external authentication state.")

            cursor.execute("""SELECT id, uid, email
                                FROM externalusers
                               WHERE provider=%s
                                 AND account=%s""",
                           (external["provider"], external["account"]))

            # Note: the token validation above implicitly checks that there's a
            # matching row in the 'externalusers' table.
            external_user_id, existing_user_id, external_email = cursor.fetchone()

            # Check that we don't already have a Critic user associated with
            # this external user.
            if existing_user_id is not None:
                existing_user = dbutils.User.fromId(db, existing_user_id)
                return OperationResult(
                    message=("There is already a Critic user ('%s') connected "
                             "to the %s '%s'" % (existing_user.name,
                                                 provider.getTitle(),
                                                 external["account"])))

            if email == external_email:
                verify_email_address = provider.configuration["verify_email_addresses"]

            # Reset 'email' column in 'externalusers': we only need it to detect
            # if the user changed the email address in the "Create user" form.
            # Also reset the 'token' column, which serves no further purpose
            # beyond this point.
            with db.updating_cursor("externalusers") as cursor:
                cursor.execute("""UPDATE externalusers
                                     SET email=NULL,
                                         token=NULL
                                   WHERE id=%s""",
                               (external_user_id,))

        email_verified = False if email and verify_email_address else None

        user = dbutils.User.create(
            db, username, fullname, email, email_verified, password,
            external_user_id=external_user_id)

        if email_verified is False:
            sendVerificationMail(db, user)

        user.sendUserCreatedMail("wsgi[registeruser]", external)

        auth.createSessionId(db, req, user)

        return OperationResult()
