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

import api
import apiobject

import configuration

class Extension(apiobject.APIObject):
    wrapper_class = api.extension.Extension

    def __init__(self, extension_id, name, publisher_id):
        self.id = extension_id
        self.name = name
        self.__publisher_id = publisher_id

    def getKey(self, critic):
        publisher = self.getPublisher(critic)
        if publisher is None:
            return self.name
        return "%s/%s" % (publisher.name, self.name)

    def getPublisher(self, critic):
        if self.__publisher_id is None:
            return None
        return api.user.fetch(critic, self.__publisher_id)

def fetch(critic, extension_id, key):
    if not configuration.extensions.ENABLED:
        raise api.extension.ExtensionError("Extension support not enabled")
    cursor = critic.getDatabaseCursor()
    if extension_id is not None:
        cursor.execute(
            """SELECT id, name, author
                 FROM extensions
                WHERE id=%s""",
            (extension_id,))
    else:
        publisher_name, _, extension_name = key.partition("/")
        if extension_name is None:
            extension_name = publisher_name
            cursor.execute(
                """SELECT id, name, author
                     FROM extensions
                    WHERE author IS NULL
                      AND name=%s""",
                (extension_name,))
        else:
            cursor.execute(
                """SELECT extensions.id, extensions.name, author
                     FROM extensions
                     JOIN users ON (users.id=author)
                    WHERE extensions.name=%s
                      AND users.name=%s""",
                (extension_name, publisher_name))
    try:
        return next(Extension.make(critic, cursor))
    except StopIteration:
        if extension_id is not None:
            raise api.extension.InvalidExtensionId(extension_id)
        else:
            raise api.extension.InvalidExtensionKey(key)

def fetchAll(critic, publisher, installed_by):
    if not configuration.extensions.ENABLED:
        raise api.extension.ExtensionError("Extension support not enabled")
    cursor = critic.getDatabaseCursor()
    if installed_by:
        if publisher:
            cursor.execute(
                """SELECT extensions.id, name, author
                     FROM extensions
                     JOIN extensioninstalls ON (extension=extensions.id)
                    WHERE author=%s
                      AND uid=%s""",
                (publisher.id, installed_by.id))
        else:
            cursor.execute(
                """SELECT extensions.id, name, author
                     FROM extensions
                     JOIN extensioninstalls ON (extension=extensions.id)
                    WHERE uid=%s""",
                (installed_by.id,))
    elif publisher:
        cursor.execute(
            """SELECT id, name, author
                 FROM extensions
                WHERE author=%s""",
            (publisher.id,))
    else:
        cursor.execute(
            """SELECT id, name, author
                 FROM extensions""")
    return list(Extension.make(critic, cursor))
