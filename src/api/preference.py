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

class InvalidPreferenceItem(api.APIError):
    """Raised if an invalid preference item is used."""

    def __init__(self, item):
        """Constructor"""
        super(InvalidPreferenceItem, self).__init__(
            "Invalid preference item: %r" % item)

class Preference(object):
    def __init__(self, item, value, user, repository):
        self.__item = item
        self.__value = value
        self.__user = user
        self.__repository = repository

    def __bool__(self):
        return bool(self.__value)
    def __int__(self):
        return self.__value
    def __str__(self):
        return self.__value

    @property
    def item(self):
        return self.__item

    @property
    def value(self):
        return self.__value

    @property
    def user(self):
        return self.__user

    @property
    def repository(self):
        return self.__repository
