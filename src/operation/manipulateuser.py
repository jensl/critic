# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
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

import re
import base64

import dbutils
import gitutils
import auth
import mailutils
import textutils
import configuration

from operation import (Operation, OperationResult, OperationError,
                       OperationFailure, Optional, User)

class SetFullname(Operation):
    def __init__(self):
        Operation.__init__(self, { "user_id": int,
                                   "value": str })

    def process(self, db, user, user_id, value):
        if user.id != user_id:
            Operation.requireRole(db, "administrator", user)

        if not value.strip():
            raise OperationError("empty display name is not allowed")

        db.cursor().execute("UPDATE users SET fullname=%s WHERE id=%s", (value.strip(), user_id))
        db.commit()

        return OperationResult()

class SetGitEmails(Operation):
    def __init__(self):
        Operation.__init__(self, { "subject": User,
                                   "value": [str] })

    def process(self, db, user, subject, value):
        if user != subject:
            Operation.requireRole(db, "administrator", user)

        for address in value:
            if not address.strip():
                raise OperationError("empty email address is not allowed")
            if address.count("@") != 1:
                raise OperationError("invalid email address")

        cursor = db.cursor()
        cursor.execute("SELECT email FROM usergitemails WHERE uid=%s", (subject.id,))

        current_addresses = set(address for (address,) in cursor)
        new_addresses = set(address.strip() for address in value)

        for address in (current_addresses - new_addresses):
            cursor.execute("DELETE FROM usergitemails WHERE uid=%s AND email=%s",
                           (subject.id, address))
        for address in (new_addresses - current_addresses):
            cursor.execute("INSERT INTO usergitemails (uid, email) VALUES (%s, %s)",
                           (subject.id, address))

        db.commit()

        return OperationResult()

class ChangePassword(Operation):
    def __init__(self):
        Operation.__init__(self, { "subject": Optional(User),
                                   "current_pw": Optional(str),
                                   "new_pw": str })

    def process(self, db, user, new_pw, subject=None, current_pw=None):
        if subject is None:
            subject = user

        cursor = db.cursor()

        if user != subject:
            Operation.requireRole(db, "administrator", user)
        elif current_pw is None:
            cursor.execute("SELECT password FROM users WHERE id=%s", (subject.id,))
            if cursor.fetchone()[0] is not None:
                # This is mostly a sanity check; the only way to trigger this is
                # if the user has no password when he loads /home, sets a
                # password in another tab or using another browser, and then
                # tries to set (rather than change) the password using the old
                # stale /home.
                raise OperationFailure(code="wrongpassword",
                                       title="Wrong password!",
                                       message="No current password provided.")

        if current_pw is not None:
            try: auth.checkPassword(db, subject.name, current_pw)
            except auth.WrongPassword:
                raise OperationFailure(code="wrongpassword",
                                       title="Wrong password!",
                                       message="The provided current password is not correct.")

        if not new_pw:
            raise OperationFailure(code="emptypassword",
                                   title="Empty password!",
                                   message="Setting an empty password is not allowed.")

        cursor.execute("UPDATE users SET password=%s WHERE id=%s",
                       (auth.hashPassword(new_pw), subject.id))

        db.commit()

        return OperationResult()

    def sanitize(self, value):
        sanitized = value.copy()
        if "current_pw" in value:
            sanitized["current_pw"] = "****"
        sanitized["new_pw"] = "****"
        return sanitized

def checkEmailAddressSyntax(address):
    return bool(re.match(r"[^@]+@[^.]+(?:\.[^.]+)*$", address))

def sendVerificationMail(db, user, email_id=None):
    cursor = db.cursor()

    if email_id is None:
        cursor.execute("""SELECT email
                            FROM users
                           WHERE id=%s""",
                       (user.id,))

        email_id, = cursor.fetchone()

    cursor.execute("""SELECT email, verification_token
                        FROM useremails
                       WHERE id=%s""",
                   (email_id,))

    email, verification_token = cursor.fetchone()

    if verification_token is None:
        verification_token = auth.getToken(encode=base64.b16encode)

        cursor.execute("""UPDATE useremails
                             SET verification_token=%s
                           WHERE id=%s""",
                       (verification_token, email_id))

    if configuration.base.ACCESS_SCHEME == "http":
        protocol = "http"
    else:
        protocol = "https"

    administrators = dbutils.getAdministratorContacts(db, indent=2)

    if administrators:
        administrators = ":\n\n%s" % administrators
    else:
        administrators = "."

    recipients = [mailutils.User(user.name, email, user.fullname)]
    subject = "[Critic] Please verify your email: %s" % email
    body = textutils.reflow("""
This is a message from the Critic code review system at %(hostname)s.  The user
'%(username)s' on this system has added this email address to his/her account.
If this is you, please confirm this by following this link:

  %(url_prefix)s/verifyemail?email=%(email)s&token=%(verification_token)s

If this is not you, you can safely ignore this email.  If you wish to report
abuse, please contact the Critic system's administrators%(administrators)s
""" % { "hostname": configuration.base.HOSTNAME,
        "username": user.name,
        "email": email,
        "url_prefix": "%s://%s" % (protocol, configuration.base.HOSTNAME),
        "verification_token": verification_token,
        "administrators": administrators })

    mailutils.sendMessage(recipients, subject, body)

class RequestVerificationEmail(Operation):
    def __init__(self):
        Operation.__init__(self, { "email_id": int })

    def process(self, db, user, email_id):
        cursor = db.cursor()
        cursor.execute("""SELECT uid, email, verified
                            FROM useremails
                           WHERE id=%s""",
                       (email_id,))

        row = cursor.fetchone()

        if not row:
            raise OperationFailure(
                code="invalidemailid",
                title="No such email address",
                message="The address might have been deleted already.")

        user_id, email, verified = row

        if verified is True:
            raise OperationFailure(
                code="alreadyverified",
                title="Address already verified",
                message="This address has already been verified.")

        if user != user_id:
            Operation.requireRole(db, "administrator", user)
            user = dbutils.User.fromId(db, user_id)

        sendVerificationMail(db, user, email_id)

        db.commit()

        return OperationResult()

class DeleteEmailAddress(Operation):
    def __init__(self):
        Operation.__init__(self, { "email_id": int })

    def process(self, db, user, email_id):
        cursor = db.cursor()
        cursor.execute("""SELECT uid
                            FROM useremails
                           WHERE id=%s""",
                       (email_id,))

        row = cursor.fetchone()

        if not row:
            raise OperationFailure(
                code="invalidemailid",
                title="No such email address",
                message="The address might have been deleted already.")

        subject_id, = row

        if user != subject_id:
            Operation.requireRole(db, "administrator", user)

        cursor.execute("""SELECT useremails.id, users.email IS NOT NULL
                            FROM useremails
                 LEFT OUTER JOIN users ON (users.email=useremails.id)
                           WHERE useremails.uid=%s""",
                       (subject_id,))

        emails = dict(cursor)

        # Reject if the user has more than one email address registered and is
        # trying to delete the selected one.  The UI checks this too, but that
        # check is not 100 % reliable since it checks the state at the time the
        # page was loaded, not necessarily the current state.
        if len(emails) > 1 and emails[email_id]:
            raise OperationFailure(
                code="notallowed",
                title="Will not delete current address",
                message=("This email address is your current address.  Please "
                         "select one of the other addresses as your current "
                         "address before deleting it."))

        cursor.execute("""UPDATE users
                             SET email=NULL
                           WHERE id=%s
                             AND email=%s""",
                       (subject_id, email_id))

        cursor.execute("""DELETE FROM useremails
                                WHERE id=%s""",
                       (email_id,))

        db.commit()

        return OperationResult()

class SelectEmailAddress(Operation):
    def __init__(self):
        Operation.__init__(self, { "email_id": int })

    def process(self, db, user, email_id):
        cursor = db.cursor()
        cursor.execute("""SELECT uid
                            FROM useremails
                           WHERE id=%s""",
                       (email_id,))

        row = cursor.fetchone()

        if not row:
            raise OperationFailure(
                code="invalidemailid",
                title="No such email address",
                message="The address might have been deleted already.")

        user_id, = row

        if user != user_id:
            Operation.requireRole(db, "administrator", user)

        cursor.execute("""UPDATE users
                             SET email=%s
                           WHERE id=%s""",
                       (email_id, user_id))

        db.commit()

        return OperationResult()

class AddEmailAddress(Operation):
    def __init__(self):
        Operation.__init__(self, { "subject": User,
                                   "email": str })

    def process(self, db, user, subject, email):
        if not checkEmailAddressSyntax(email):
            raise OperationFailure(
                code="invalidemail",
                title="Invalid email address",
                message="Please provide an address on the form <user>@<host>!")

        if user != subject:
            Operation.requireRole(db, "administrator", user)

        cursor = db.cursor()
        cursor.execute("""SELECT 1
                            FROM useremails
                           WHERE uid=%s
                             AND email=%s""",
                       (subject.id, email))

        if cursor.fetchone():
            raise OperationFailure(
                code="invalidemail",
                title="Duplicate email address",
                message="The exact same address is already registered!")

        if user.hasRole(db, "administrator"):
            verified = None
        elif configuration.base.VERIFY_EMAIL_ADDRESSES:
            verified = False
        else:
            verified = None

        cursor.execute("""INSERT INTO useremails (uid, email, verified)
                               VALUES (%s, %s, %s)
                            RETURNING id""",
                       (subject.id, email, verified))

        email_id, = cursor.fetchone()

        if verified is False:
            sendVerificationMail(db, subject, email_id)

        if subject.email is None:
            cursor.execute("""UPDATE users
                                 SET email=%s
                               WHERE id=%s""",
                           (email_id, subject.id))

        db.commit()

        return OperationResult()
