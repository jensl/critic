# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2013 Martin Olsson
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

import configuration

def getInstalledSHA1(db):
    cursor = db.cursor()
    cursor.execute("SELECT installed_sha1 FROM systemidentities WHERE name=%s", (configuration.base.SYSTEM_IDENTITY,))
    return cursor.fetchone()[0]

def getURLPrefix(db, user=None):
    cursor = db.cursor()
    cursor.execute("""SELECT anonymous_scheme, authenticated_scheme, hostname
                        FROM systemidentities
                       WHERE name=%s""",
                   (configuration.base.SYSTEM_IDENTITY,))
    anonymous_scheme, authenticated_scheme, hostname = cursor.fetchone()
    if user and not user.isAnonymous():
        scheme = authenticated_scheme
    else:
        scheme = anonymous_scheme
    return "%s://%s" % (scheme, hostname)

def getAdministratorContacts(db, indent=0, as_html=False):
    import dbutils
    administrators = dbutils.User.withRole(db, "administrator")

    # Sort by id, IOW, by user creation time.  Probably gives "primary"
    # administrator first and auxiliary administrators second, but might also
    # just be arbitrary.  If nothing else, it makes the order stable.
    administrators = sorted(administrators, key=lambda user: user.id)

    # Skip administrators with no email addresses, since those are unhelpful in
    # this context.
    administrators = filter(lambda user: user.email, administrators)

    if as_html:
        result = "the system administrator"

        if not administrators:
            return result
        if len(administrators) > 1:
            result += "s"

        result += " (%s)"

        mailto_links = \
            [("<a href='mailto:%(email)s'>%(fullname)s</a>"
              % { "email": user.email, "fullname": user.fullname })
             for user in administrators]

        if len(mailto_links) == 1:
            return result % mailto_links[0]
        else:
            return result % ("one of %s or %s" % (", ".join(mailto_links[:-1]),
                                                  mailto_links[-1]))
    else:
        if not administrators:
            return ""

        administrators = ["%s <%s>" % (user.fullname, user.email)
                          for user in administrators]

        prefix = " " * indent
        return prefix + ("\n" + prefix).join(administrators)
