# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2015 the Critic contributors, Opera Software ASA
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

import hashlib
import threading
import time

import auth
import dbutils
import configuration

def escaped(fields, fn):
    return { identifier: fn(value)
             for identifier, value in fields.items() }

class LDAPCache(object):
    def __init__(self, max_age):
        self.lock = threading.Lock()
        # sha256(repr(fields)) => (user_id, timestamp)
        self.cache = {}
        self.max_age = max_age

    @staticmethod
    def __key(fields):
        return hashlib.sha256(repr(sorted(fields.items()))).hexdigest()

    def get(self, fields):
        # A max age of zero (or less) means the cache is disabled.
        if self.max_age <= 0:
            return None
        with self.lock:
            key = LDAPCache.__key(fields)
            value, timestamp = self.cache.get(key, (None, None))
            if value is None:
                return None
            if time.time() - timestamp > self.max_age:
                del self.cache[key]
                return None
            return value

    def set(self, fields, value):
        # A max age of zero (or less) means the cache is disabled.
        if self.max_age <= 0:
            return
        with self.lock:
            # Note: We might overwrite an existing (presumably identical) entry
            # here, due to two threads racing to authenticate the same user.
            key = LDAPCache.__key(fields)
            self.cache[key] = (value, time.time())

class LDAP(auth.Database):
    def __init__(self):
        super(LDAP, self).__init__("ldap")
        self.cache = LDAPCache(self.configuration["cache_max_age"])

    def __startConnection(self):
        import ldap
        connection = ldap.initialize(self.configuration["url"])
        if self.configuration["use_tls"]:
            connection.start_tls_s()
        bind_dn = self.configuration["bind_dn"]
        bind_password = self.configuration["bind_password"]
        if bind_dn is not None and bind_password is not None:
            connection.simple_bind_s(bind_dn, bind_password)
        return connection

    def __isMemberOfGroup(self, connection, group, fields):
        import ldap
        result = connection.search_s(
            group["dn"], ldap.SCOPE_BASE,
            attrlist=[group["members_attribute"]])
        if len(result) != 1:
            raise auth.AuthenticationError(
                "Required group '%s' not found" % group["dn"])
        group_dn, group_attributes = result[0]
        if group["members_attribute"] not in group_attributes:
            raise auth.AuthenticationError(
                "Required group '%s' has no attribute '%s'"
                % (group["dn"], group["members_attribute"]))
        members = group_attributes[group["members_attribute"]]
        member_value = (group["member_value"]
                        % escaped(fields, ldap.dn.escape_dn_chars))
        return member_value in members

    def getFields(self):
        return self.configuration["fields"]

    def authenticate(self, db, fields):
        import ldap
        import ldap.filter

        cached_data = self.cache.get(fields)
        if cached_data is not None:
            cached_user_id, cached_authentication_labels = cached_data
            try:
                user = dbutils.User.fromId(db, cached_user_id)
            except dbutils.InvalidUserId:
                pass
            else:
                db.setUser(user, cached_authentication_labels)
                return

        connection = self.__startConnection()

        search_base = (self.configuration["search_base"]
                       % escaped(fields, ldap.dn.escape_dn_chars))
        search_filter = (self.configuration["search_filter"]
                         % escaped(fields, ldap.filter.escape_filter_chars))

        attributes = [self.configuration["username_attribute"]]

        if self.configuration["create_user"]:
            attributes.extend([self.configuration["fullname_attribute"],
                               self.configuration["email_attribute"]])

        result = connection.search_s(
            search_base, ldap.SCOPE_SUBTREE, search_filter, attributes)

        if not result:
            raise auth.AuthenticationFailed("LDAP search found no matches")

        if len(result) > 1:
            raise auth.AuthenticationFailed("LDAP search found multiple matches")

        dn, attributes = result[0]

        # fields_with_dn = fields.copy()
        # fields_with_dn["dn"] = dn

        try:
            connection.simple_bind_s(
                dn, fields[self.configuration["credentials"]])
        except ldap.INVALID_CREDENTIALS:
            raise auth.AuthenticationFailed("Invalid credentials")
        except ldap.UNWILLING_TO_PERFORM:
            # Might be raised for e.g. empty password.
            raise auth.AuthenticationFailed("Invalid credentials")

        authentication_labels = set()

        if "require_groups" in self.configuration:
            for group in self.configuration["require_groups"]:
                if not self.__isMemberOfGroup(connection, group, fields):
                    raise auth.AuthenticationFailed(
                        "Not member of required LDAP groups")
                if "label" in group:
                    authentication_labels.add(group["label"])

        if "additional_groups" in self.configuration:
            for group in self.configuration["additional_groups"]:
                if self.__isMemberOfGroup(connection, group, fields):
                    authentication_labels.add(group["label"])

        connection.unbind_s()

        def getAttribute(name, defvalue=None):
            value_list = attributes.get(name)
            if value_list is None or not value_list or not value_list[0]:
                defvalue
            return value_list[0]

        username = getAttribute(self.configuration["username_attribute"])

        if username is None:
            raise auth.AuthenticationError(
                "Configured username LDAP attribute missing")

        try:
            user = dbutils.User.fromName(db, username)
        except dbutils.NoSuchUser:
            if not self.configuration["create_user"]:
                raise auth.AuthenticationFailed("No matching Critic user found")

            fullname = getAttribute(self.configuration["fullname_attribute"],
                                    username)
            email = getAttribute(self.configuration["email_attribute"])

            user = dbutils.User.create(
                db, username, fullname, email, email_verified=None)

        db.setUser(user, authentication_labels)

        self.cache.set(fields, (user.id, authentication_labels))

    def getAuthenticationLabels(self, user):
        connection = self.__startConnection()

        fields = self.configuration["fields_from_user"](user)
        authentication_labels = set()

        if "require_groups" in self.configuration:
            for group in self.configuration["require_groups"]:
                if "label" in group \
                        and self.__isMemberOfGroup(connection, group, fields):
                    authentication_labels.add(group["label"])

        if "additional_groups" in self.configuration:
            for group in self.configuration["additional_groups"]:
                if self.__isMemberOfGroup(connection, group, fields):
                    authentication_labels.add(group["label"])

        return authentication_labels

if configuration.auth.DATABASE == "ldap":
    auth.DATABASE = LDAP()
