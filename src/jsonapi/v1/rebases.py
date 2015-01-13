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
    value_class = api.log.rebase.Rebase
    exceptions = api.log.rebase.InvalidRebaseId

    @staticmethod
    def json(value, parameters, linked):
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
                 "review": value.review.id,
                 "creator": value.creator.id,
                 "old_head": old_head.id,
                 "new_head": new_head.id }

        linked_commits = set([old_head, new_head])

        if isinstance(value, api.log.rebase.HistoryRewrite):
            data.update({ "type": "history-rewrite" })
        else:
            old_upstream = value.old_upstream
            new_upstream = value.new_upstream

            linked_commits.update([old_upstream, new_upstream])

            equivalent_merge = value.equivalent_merge
            if equivalent_merge:
                linked_commits.add(equivalent_merge)
                equivalent_merge = equivalent_merge.id

            replayed_rebase = value.replayed_rebase
            if replayed_rebase:
                linked_commits.add(replayed_rebase)
                replayed_rebase = replayed_rebase.id

            data.update({ "type": "move",
                          "old_upstream": old_upstream.id,
                          "new_upstream": new_upstream.id,
                          "equivalent_merge": equivalent_merge,
                          "replayed_rebase": replayed_rebase })

        linked.add(jsonapi.v1.reviews.Reviews, value.review)
        linked.add(jsonapi.v1.users.Users, value.creator)
        linked.add(jsonapi.v1.commits.Commits, *linked_commits)

        return parameters.filtered("rebases", data)

    @staticmethod
    def single(critic, argument, parameters):
        """Retrieve one (or more) rebases in this system.

           REBASE_ID : integer

           Retrieve a rebase identified by its unique numeric id."""

        return Rebases.setAsContext(parameters, api.log.rebase.fetch(
            critic, rebase_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(critic, parameters):
        """Retrieve all rebases in this system.

           review : REVIEW_ID : -

           Include only rebases of one review, identified by the review's unique
           numeric id."""

        review = jsonapi.v1.reviews.Reviews.deduce(critic, parameters)
        return api.log.rebase.fetchAll(critic, review=review)

    @staticmethod
    def setAsContext(parameters, rebase):
        parameters.setContext(Rebases.name, rebase)
        # Also set the rebase's review (and repository and branch) as context.
        jsonapi.v1.reviews.Reviews.setAsContext(parameters, rebase.review)
        return rebase
