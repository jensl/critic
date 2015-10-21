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

class FilterError(api.APIError):
    """Base exception for all errors related to the User class."""
    pass

class Filter(api.APIObject):
    """Base class of RepositoryFilter and ReviewFilter"""

    @property
    def subject(self):
        """The filter's subject

           The subject is the user that the filter applies to."""
        return self._impl.getSubject(self.critic)

    @property
    def type(self):
        """The filter's type

           The type is always one of "reviewer", "watcher" and "ignore"."""
        return self._impl.type

    @property
    def path(self):
        """The filter's path"""
        return self._impl.path

class InvalidRepositoryFilterId(FilterError):
    """Raised when an invalid repository filter id is used"""

    def __init__(self, value):
        """Constructor"""
        super(InvalidRepositoryFilterId, self).__init__(
            "Invalid repository filter id: %r" % value)
        self.value = value

class RepositoryFilter(Filter):
    """Representation of a repository filter

       A repository filter is a filter that applies to all reviews in a
       repository."""

    @property
    def id(self):
        """The repository filter's unique id"""
        return self._impl.id

    @property
    def repository(self):
        """The repository filter's repository"""
        return self._impl.getRepository(self.critic)

    @property
    def delegates(self):
        """The repository filter's delegates, or None

           The delegates are returned as a frozenset of api.user.User objects.
           If the filter's type is not "reviewer", this attribute's value is
           None."""
        return self._impl.getDelegates(self.critic)

def fetchRepositoryFilter(critic, filter_id):
    """Fetch a RepositoryFilter object with the given filter id"""
    assert isinstance(critic, api.critic.Critic)
    return api.impl.filters.fetchRepositoryFilter(critic, int(filter_id))

class ReviewFilter(Filter):
    """Representation of a review filter

       A review filter is a filter that applies to a single review only."""

    @property
    def id(self):
        """The review filter's unique id"""
        return self._impl.id

    @property
    def review(self):
        """The review filter's review"""
        return self._impl.getReview(self.critic)

    @property
    def creator(self):
        """The review filter's creator

           This is the user that created the review filter, which can be
           different from the filter's subject."""
        return self._impl.getCreator(self.critic)
