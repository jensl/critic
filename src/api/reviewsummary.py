# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

class ReviewSummaryError(api.APIError):
    pass

class ReviewSummaryContainer(api.APIObject):
    """Container object for review summaries"""

    @property
    def reviews(self):
        return self._impl.reviews

    @property
    def more(self):
        return self._impl.more

class ReviewSummary(api.APIObject):
    """Representation of a review summary"""

    TYPE_VALUES = frozenset(["all", "own", "other"])

    @property
    def review(self):
        return self._impl.review

    @property
    def latest_change(self):
        return self._impl.latest_change

def fetchMany(critic, search_type, user, count, offset):
    """Fetch the dashboard for user"""

    import api.impl
    assert search_type is not None
    if user is None:
        assert search_type == "all"
    assert isinstance(search_type, str)
    assert isinstance(user, api.user.User) or user is None
    assert search_type in ReviewSummary.TYPE_VALUES
    assert count is None or isinstance(count, int)
    assert offset is None or isinstance(offset, int)
    if count is not None:
        assert count > 0
    if offset is not None:
        assert offset >= 0
    return api.impl.reviewsummary.fetchMany(critic, search_type, user, count, offset)
