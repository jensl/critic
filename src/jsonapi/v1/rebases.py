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
    exceptions = api.log.rebase.RebaseError

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
    def create(parameters, value, values, data):
        critic = parameters.critic
        user = critic.actual_user

        converted = jsonapi.convert(
            parameters,
            {
                "new_upstream?": str,
                "history_rewrite?": bool
            },
            data)

        new_upstream = converted.get("new_upstream")
        history_rewrite = converted.get("history_rewrite")

        if (new_upstream is None) == (history_rewrite is None):
            raise jsonapi.UsageError(
                "Exactly one of the arguments new_upstream and history_rewrite "
                "must be specified.")

        if history_rewrite == False:
            raise jsonapi.UsageError(
                "history_rewrite must be true, or omitted.")

        review = jsonapi.deduce("v1/reviews", parameters)

        if review is None:
            raise jsonapi.UsageError(
                "review must be specified when preparing a rebase")

        if history_rewrite is not None:
            expected_type = api.log.rebase.HistoryRewrite
        else:
            expected_type = api.log.rebase.MoveRebase

        result = []

        def collectRebase(rebase):
            assert isinstance(rebase, expected_type), repr(rebase)
            result.append(rebase)

        with api.transaction.Transaction(critic) as transaction:
            transaction \
                .modifyReview(review) \
                .prepareRebase(
                    user, new_upstream, history_rewrite,
                    callback=collectRebase)

        assert len(result) == 1, repr(result)
        return result[0], None

    @staticmethod
    def delete(parameters, value, values):
        critic = parameters.critic

        if value is None:
            raise jsonapi.UsageError(
                "Only one rebase can currently be deleted per request")
        rebase = value

        with api.transaction.Transaction(critic) as transaction:
            transaction \
                .modifyReview(rebase.review) \
                .cancelRebase(rebase)

    @staticmethod
    def setAsContext(parameters, rebase):
        parameters.setContext(Rebases.name, rebase)
        # Also set the rebase's review (and repository and branch) as context.
        jsonapi.v1.reviews.Reviews.setAsContext(parameters, rebase.review)
        return rebase
