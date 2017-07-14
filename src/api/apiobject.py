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

class APIObject(object):
    """Base class of all significant API classes

       Exposes the Critic session object as the read-only 'critic' attribute.

       Also holds the reference to the internal implementation object, which
       should only be used in the implementation of the API."""

    def __init__(self, critic, impl):
        self.__critic = critic
        self.__impl = impl

    def __hash__(self):
        return hash(int(self))
    def __eq__(self, other):
        return int(self) == int(other)

    @property
    def critic(self):
        """The Critic session object used to create the API object"""
        return self.__critic

    def refresh(self):
        """Refresh cached information from the database

           This function is called automatically when the current database
           transaction is committed, so there is normally no reason to call it
           directly."""
        self.__impl = self.__impl.refresh(self.__critic)

    @property
    def _impl(self):
        """Underlying object implementation

           This value should not be used outside the implementation of
           the API."""
        return self.__impl

    def _set_impl(self, impl):
        """Set the underlying object implementation

           This method should not be called outside the implementation
           of the API."""
        self.__impl = impl
