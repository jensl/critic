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
import jsonapi

@jsonapi.PrimaryResource
class ReviewSummaries(object):
    """Review summaries"""

    name = "reviewsummaries"
    value_class = api.reviewsummary.ReviewSummaryContainer
    exceptions = (api.reviewsummary.ReviewSummaryError,)

    @staticmethod
    def json(value, parameters):
        """ReviewSummaries {
             "reviews": ReviewSummary[],
             "more": bool // true if there are more reviews than the ones retrieved
           }

           ReviewSummary {
             "review": integer,
             "summary": string, // the review's summary (text)
             "latest_change": integer, // the timestamp of the latest commit or comment
             "progress": float, // reviewing progress as a number between 0 and 1
             "issues": integer, // the number of open issues in the review
           }"""

        def review_summary_as_dict(review_summary):
            return { "review": review_summary.review,
                     "summary": review_summary.review.summary,
                     "latest_change": review_summary.latest_change,
                     "progress": review_summary.review.total_progress,
                     "issues": len(review_summary.review.open_issues)}

        return parameters.filtered(
            "review summaries", { "reviews": [review_summary_as_dict(review_summary) for
                                              review_summary in value.reviews],
                                  "more": value.more})

    @staticmethod
    def multiple(parameters):
        """Retrieve review summaries."""

        countParameter = parameters.getQueryParameter("count")
        offsetParameter = parameters.getQueryParameter("offset")
        count = int(countParameter) if countParameter is not None else None
        offset = int(offsetParameter) if offsetParameter is not None else None
        if count < 1 and count is not None:
            jsonapi.InputError("count parameter must be bigger than 0")
        if offset < 0 and offset is not None:
            jsonapi.InputError("offset can't be less than 0")

        search_type = parameters.getQueryParameter("type")
        user = parameters.critic.actual_user

        if user is None and search_type != "all":
            raise jsonapi.PermissionDenied(
                "You do not have the rights to access this resource")

        if search_type not in api.reviewsummary.ReviewSummary.TYPE_VALUES:
            raise jsonapi.UsageError(
                "Review summary type parameter must be specified and set to "
                "one of: " + \
                ", ".join(api.reviewsummary.ReviewSummary.TYPE_VALUES))
        return api.reviewsummary.fetchMany(parameters.critic, search_type, user, count, offset)
