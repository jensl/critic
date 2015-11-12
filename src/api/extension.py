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

class ExtensionError(api.APIError):
    """Base exception for all errors related to the Extension class"""
    pass

class InvalidExtensionId(ExtensionError):
    """Raised when a invalid extension id is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidExtensionId, self).__init__(
            "Invalid extension id: %r" % value)
        self.value = value

class InvalidExtensionKey(ExtensionError):
    """Raised when an invalid extension key is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidExtensionKey, self).__init__(
            "Invalid extension key: %r" % value)
        self.value = value

class Extension(api.APIObject):
    """Representation of a Critic extension"""

    def __int__(self):
        return self.id
    def __hash__(self):
        return hash(int(self))
    def __eq__(self, other):
        return int(self) == int(other)

    @property
    def id(self):
        """The extension's unique id"""
        return self._impl.id

    @property
    def name(self):
        """The extension's name"""
        return self._impl.name

    @property
    def key(self):
        """The extension's unique key

           For a system extension, the key is the extension's name.  For other
           extensions, the key is the publisher's username followed by a slash
           followed by the extension's name."""
        return self._impl.getKey(self.critic)

    @property
    def publisher(self):
        """The extension's publisher

           The user that published the extension.  This may not be the author
           (who may not be a user of this Critic system.)

           None if this is a system extension."""
        return self._impl.getPublisher(self.critic)

    @property
    def default_version(self):
        """The default extension version

           This is typically the version whose extension description and other
           metadata should be presented as the extension's true metadata."""
        return self._impl.getDefaultVersion()

def fetch(critic, extension_id=None, key=None):
    """Fetch an Extension object with the given extension id or key

       Exactly one of the 'extension_id' and 'key' arguments can be used.

       Exceptions:

         InvalidExtensionId: if 'extension_id' is used and is not a valid
                             extension id.
         InvalidExtensionKey: if 'key' is used and is not a valid extensions
                              key."""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert (extension_id is None) != (key is None)
    return api.impl.extension.fetch(critic, extension_id, key)

def fetchAll(critic, publisher=None, installed_by=None):
    """Fetch Extension objects for all extensions in the system

       If 'publisher' is not None, it must be an api.user.User object, and only
       extensions published by this user are returned.

       If 'installed_by' is not None, it must be an api.user.User object, and
       only extensions that this user has installed are returned.  This may
       include extensions that are universally installed (i.e. installed for all
       users, and not by this user directly.)"""
    import api.impl
    assert isinstance(critic, api.critic.Critic)
    assert publisher is None or isinstance(publisher, api.user.User)
    assert installed_by is None or isinstance(installed_by, api.user.User)
    return api.impl.extension.fetchAll(critic, publisher, installed_by)
