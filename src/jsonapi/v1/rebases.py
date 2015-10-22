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
import jsonapi

@jsonapi.PrimaryResource
class Rebases(object):
    """The review rebases in this system."""

    name = "rebases"
    contexts = (None, "reviews")
    value_class = (api.log.rebase.MoveRebase, api.log.rebase.HistoryRewrite)
    exceptions = api.log.rebase.InvalidRebaseId

    @staticmethod
    def json(value, parameters):
        """{
             "id": integer,
             "review": integer,
             "creator": integer,
             "type": "history-rewrite" or "move"
             "old_head": integer,
             "new_head": integer,
             // if |type| is "move":
             "old_upstream": integer,
             "new_upstream": integer,
             "equivalent_merge": integer or null,
             "replayed_rebase": integer or null,
           }"""

        old_head = value.old_head
        new_head = value.new_head

        data = { "id": value.id,
                 "review": value.review,
                 "creator": value.creator,
                 "old_head": old_head,
                 "new_head": new_head }

        if isinstance(value, api.log.rebase.HistoryRewrite):
            data.update({ "type": "history-rewrite" })
        else:
            data.update({ "type": "move",
                          "old_upstream": value.old_upstream,
                          "new_upstream": value.new_upstream,
                          "equivalent_merge": value.equivalent_merge,
                          "replayed_rebase": value.replayed_rebase })

        return parameters.filtered("rebases", data)

    @staticmethod
    def single(parameters, argument):
        """Retrieve one (or more) rebases in this system.

           REBASE_ID : integer

           Retrieve a rebase identified by its unique numeric id."""

        return Rebases.setAsContext(parameters, api.log.rebase.fetch(
            parameters.critic, rebase_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(parameters):
        """Retrieve all rebases in this system.

           review : REVIEW_ID : -

           Include only rebases of one review, identified by the review's unique
           numeric id."""

        review = jsonapi.deduce("v1/reviews", parameters)
        return api.log.rebase.fetchAll(parameters.critic, review=review)

    @staticmethod
    def setAsContext(parameters, rebase):
        parameters.setContext(Rebases.name, rebase)
        # Also set the rebase's review (and repository and branch) as context.
        jsonapi.v1.reviews.Reviews.setAsContext(parameters, rebase.review)
        return rebase
