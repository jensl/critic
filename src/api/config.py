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

class ConfigurationError(api.APIError):
    pass

class InvalidGroup(ConfigurationError):
    def __init__(self, name):
        super(ConfigurationError, self).__init__(
            "Invalid configuration group: %s" % name)

class InvalidKey(ConfigurationError):
    def __init__(self, group, name):
        super(ConfigurationError, self).__init__(
            "Invalid configuration key: %s::%s" % (group, name))

class WrongType(ConfigurationError):
    def __init__(self, group, name, read_as):
        super(ConfigurationError, self).__init__(
            "Wrong type: %s::%s (read as %s)" % (group, name, read_as))

def getValue(group, key):
    import configuration
    if not hasattr(configuration, group):
        raise InvalidGroup(group)
    module = getattr(configuration, group)
    if not hasattr(module, key):
        raise InvalidKey(group, key)
    return getattr(module, key)

def getBoolean(group, key):
    value = getValue(group, key)
    if not isinstance(value, bool):
        raise WrongType(group, key, "boolean")
    return value

def getInteger(group, key):
    value = getValue(group, key)
    if not isinstance(value, int):
        raise WrongType(group, key, "integer")
    return value

def getString(group, key):
    value = getValue(group, key)
    if not isinstance(value, basestring):
        raise WrongType(group, key, "string")
    return value
