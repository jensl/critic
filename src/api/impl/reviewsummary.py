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

from operator import itemgetter
import calendar
from datetime import datetime

import api
import api.impl
from . import apiobject

class ReviewSummaryContainer(apiobject.APIObject):
    wrapper_class = api.reviewsummary.ReviewSummaryContainer
    def __init__(self, review_summaries, more):
        self.reviews = review_summaries
        self.more = more

class ReviewSummary(apiobject.APIObject):
    wrapper_class = api.reviewsummary.ReviewSummary
    def __init__(self, review, latest_change):
        self.review = review
        self.latest_change = latest_change

def fetchMany(critic, search_type, user, count, offset):
    cursor = critic.getDatabaseCursor()
    if count is None:
        count = 10
    if offset is None:
        offset = 0

    if search_type == "own" or search_type == "other":
        cursor.execute(
            """SELECT DISTINCT reviews.id
                 FROM reviews
                 JOIN reviewusers ON (reviewusers.review=reviews.id)
                WHERE reviews.state='open'
                  AND reviewusers.uid=%s
                  AND reviewusers.owner=%s""",
            (user.id, search_type=="own"))
    else:
        cursor.execute(
            """SELECT DISTINCT reviews.id
                 FROM reviews
                WHERE reviews.state='open'""")
    rows = cursor.fetchall()
    review_ids = [row[0] for row in rows]

    cursor.execute(
        """SELECT reviewchangesets.review,
                  MAX(commits.commit_time) AS latest_change
             FROM commits
             JOIN changesets ON (changesets.child=commits.id)
             JOIN reviewchangesets ON (reviewchangesets.changeset=changesets.id)
            WHERE reviewchangesets.review=ANY (%s)
         GROUP BY reviewchangesets.review""",
        (review_ids,))

    latest_commits = {}
    for review_id, latest_timestamp in cursor:
        if isinstance(latest_timestamp, str): # sqlite3 returns a string
            latest_commits[review_id] = calendar.timegm(datetime.strptime(
                latest_timestamp, "%Y-%m-%d %H:%M:%S").timetuple())
        else:
            latest_commits[review_id] = calendar.timegm(latest_timestamp.timetuple())

    cursor.execute(
        """SELECT commentchains.review, MAX(comments.time) AS latest_change
             FROM comments
             JOIN commentchains ON (commentchains.id=comments.chain)
            WHERE commentchains.review=ANY (%s)
              AND (comments.state='current' OR comments.state='edited')
         GROUP BY commentchains.review""",
        (review_ids,))

    latest_comments = {}
    for review_id, latest_timestamp in cursor:
        if isinstance(latest_timestamp, datetime):
            latest_comments[review_id] = calendar.timegm(
                latest_timestamp.timetuple())
        else:
            latest_comments[review_id] = latest_timestamp

    latest_changes = []
    for review_id in review_ids:
        latest_change = max(latest_commits.get(review_id),
                            latest_comments.get(review_id))
        if latest_change is not None:
            latest_changes.append((latest_change, review_id))

    latest_sorted_changes = sorted(
        latest_changes, reverse=True)[offset:offset+count]

    sorted_reviews = [
        review_id
        for _, review_id
        in latest_sorted_changes
    ]

    review_objects = api.review.fetchMany(critic, sorted_reviews)

    review_summaries = [
        ReviewSummary(review, latest_change[0]).wrap(critic)
        for review, latest_change
        in zip(review_objects, latest_sorted_changes)
    ]

    has_more = len(latest_changes) > len(review_summaries) + offset

    return ReviewSummaryContainer(review_summaries, has_more).wrap(critic)
