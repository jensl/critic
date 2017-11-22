/* -*- mode: js; indent-tabs-mode: nil -*-

 Copyright 2013 Jens Lindström, Opera Software ASA

 Licensed under the Apache License, Version 2.0 (the "License"); you may not
 use this file except in compliance with the License.  You may obtain a copy of
 the License at

   http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 License for the specific language governing permissions and limitations under
 the License.

*/

"use strict"

function CriticDashboard(user) {
    if (!(user instanceof CriticUser))
        throw CriticError("invalid user argument; expected User object")

    this.user = user

    var self = this

    var owned_finished = null
    var owned_accepted = null
    var owned_pending = null
    var owned_dropped = null

    var active = null
    var inactive = null

    function createReviews(result, filter) {
        var reviews = []

        for (var index = 0; index < result.length; ++index) {
            var review = new CriticReview(result[index].id)
            if (!filter || filter(review)) reviews.push(review)
        }

        return Object.freeze(reviews)
    }

    function getOwnedFinished() {
        if (!owned_finished)
            owned_finished = createReviews(
                db.execute(
                    "SELECT id FROM reviews JOIN reviewusers ON (review=id) WHERE uid=%d AND owner AND state='closed' ORDER BY id ASC",
                    self.user.id
                )
            )
        return owned_finished
    }

    function getOwnedAccepted() {
        if (!owned_accepted) {
            var owned_open = createReviews(
                db.execute(
                    "SELECT id FROM reviews JOIN reviewusers ON (review=id) WHERE uid=%d AND owner AND state='open' ORDER BY id ASC",
                    self.user.id
                )
            )

            owned_accepted = []
            owned_pending = []

            for (var index = 0; index < owned_open.length; ++index) {
                var review = owned_open[index]
                if (review.progress.accepted) owned_accepted.push(review)
                else owned_pending.push(review)
            }

            Object.freeze(owned_accepted)
            Object.freeze(owned_pending)
        }

        return owned_accepted
    }

    function getOwnedPending() {
        if (!owned_pending)
            /* Populates owned_pending as a side-effect. */
            getOwnedAccepted()
        return owned_pending
    }

    function getOwnedDropped() {
        if (!owned_dropped)
            owned_dropped = createReviews(
                db.execute(
                    "SELECT id FROM reviews JOIN reviewusers ON (review=id) WHERE uid=%d AND owner AND state='dropped' ORDER BY id ASC",
                    self.user.id
                )
            )
        return owned_dropped
    }

    function getActive() {
        if (!active) {
            active = []

            Object.defineProperties(active, {
                hasPendingChanges: { value: Object.create(null) },
                hasUnreadComments: { value: Object.create(null) },
                unsharedPendingChanges: { value: Object.create(null) },
                sharedPendingChanges: { value: Object.create(null) },
                unreadComments: { value: Object.create(null) },
                isReviewer: { value: Object.create(null) },
                isWatcher: { value: Object.create(null) },
            })

            var assignments = db.execute(
                "SELECT DISTINCT reviews.id AS id, fullreviewuserfiles.state AS state FROM reviews JOIN fullreviewuserfiles ON (review=id) WHERE assignee=%d AND reviews.state='open'",
                self.user.id
            )
            var is_reviewer = {}

            for (var index = 0; index < assignments.length; ++index) {
                var row = assignments[index]
                var review_id = row.id
                if (row.state == "pending") {
                    var review = new CriticReview(review_id)
                    active.push(review)
                    active.hasPendingChanges[review_id] = review
                    active.isReviewer[review_id] = review
                }
                is_reviewer[review_id] = true
            }

            var before = Date.now()

            for (var review_id in active.hasPendingChanges) {
                var pending = db.execute(
                    "SELECT SUM(reviewfiles.deleted) AS deleted, " +
                        "       SUM(reviewfiles.inserted) AS inserted, " +
                        "       EXTRACT('epoch' FROM (NOW() - MIN(reviewuserfiles.time))) AS seconds, " +
                        "       reviewfilesharing.reviewers<2 AS unshared " +
                        "FROM reviews " +
                        "JOIN reviewfiles ON (reviewfiles.review=reviews.id) " +
                        "JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id " +
                        "                     AND reviewuserfiles.uid=%d) " +
                        "JOIN reviewfilesharing ON (reviewfilesharing.review=reviews.id " +
                        "                       AND reviewfilesharing.file=reviewfiles.id) " +
                        "WHERE reviews.id=%d " +
                        "  AND reviewfiles.state='pending' " +
                        "GROUP BY reviewfilesharing.reviewers<2",
                    self.user.id,
                    review_id
                )

                for (var index = 0; index < pending.length; ++index) {
                    var row = pending[index]
                    if (row.unshared)
                        active.unsharedPendingChanges[
                            review_id
                        ] = Object.freeze({
                            deleted: row.deleted,
                            inserted: row.inserted,
                            seconds: row.seconds,
                        })
                    else
                        active.sharedPendingChanges[review_id] = Object.freeze({
                            deleted: row.deleted,
                            inserted: row.inserted,
                            seconds: row.seconds,
                        })
                }
            }

            var after = Date.now()

            active.qt = after - before

            var with_unread = db.execute(
                "SELECT reviews.id AS id, COUNT(comments.id) AS count FROM reviews JOIN commentchains ON (commentchains.review=reviews.id) JOIN comments ON (comments.chain=commentchains.id) JOIN commentstoread ON (commentstoread.comment=comments.id) WHERE commentstoread.uid=%d AND reviews.state='open' GROUP BY reviews.id",
                self.user.id
            )

            for (var index = 0; index < with_unread.length; ++index) {
                var review_id = with_unread[index].id,
                    review = active.hasPendingChanges[review_id]
                if (!review) active.push((review = new CriticReview(review_id)))
                active.hasUnreadComments[review_id] = review
                active.unreadComments[review_id] = with_unread[index].count
                if (is_reviewer[review_id])
                    active.isReviewer[review_id] = review
                else active.isWatcher[review_id] = review
            }

            active.sort(function(a, b) {
                switch (true) {
                    case a.id < b.id:
                        return -1
                    case a.id > b.id:
                        return 1
                    default:
                        return 0
                }
            })

            Object.freeze(active.hasPendingChanges)
            Object.freeze(active.hasUnreadComments)
            Object.freeze(active.unsharedPendingChanges)
            Object.freeze(active.sharedPendingChanges)
            Object.freeze(active.unreadComments)
            Object.freeze(active.isReviewer)
            Object.freeze(active.isWatcher)
            Object.freeze(active)
        }

        return active
    }

    function getInactive() {
        if (!inactive) {
            inactive = []

            Object.defineProperties(inactive, {
                isReviewer: { value: {} },
                isWatcher: { value: {} },
            })

            var is_reviewer = db.execute(
                "SELECT DISTINCT reviews.id AS id, fullreviewuserfiles.state AS state FROM reviews JOIN fullreviewuserfiles ON (review=id) WHERE assignee=%d AND reviews.state='open'",
                self.user.id
            )
            var include = {},
                exclude = {}

            for (var index = 0; index < is_reviewer.length; ++index) {
                var review_id = is_reviewer[index].id
                if (is_reviewer[index].state == "pending")
                    exclude[review_id] = true
                else include[review_id] = true
            }

            for (var review_id in include)
                if (!exclude[review_id]) {
                    var review = new CriticReview(~~review_id)
                    inactive.push(review)
                    inactive.isReviewer[review_id] = review
                }

            var is_watcher = db.execute(
                "SELECT id FROM reviews JOIN reviewusers ON (review=id) WHERE uid=%d AND state='open'",
                self.user.id
            )

            for (var index = 0; index < is_watcher.length; ++index) {
                var review_id = is_watcher[index].id
                if (!include[review_id] && !exclude[review_id]) {
                    var review = new CriticReview(review_id)
                    inactive.push(review)
                    inactive.isWatcher[review_id] = review
                }
            }

            inactive.sort(function(a, b) {
                switch (true) {
                    case a.id < b.id:
                        return -1
                    case a.id > b.id:
                        return 1
                    default:
                        return 0
                }
            })

            Object.freeze(inactive.isReviewer)
            Object.freeze(inactive.isWatcher)
            Object.freeze(inactive)
        }

        return inactive
    }

    this.owned = Object.create(null, {
        finished: { get: getOwnedFinished, enumerable: true },
        accepted: { get: getOwnedAccepted, enumerable: true },
        pending: { get: getOwnedPending, enumerable: true },
        dropped: { get: getOwnedDropped, enumerable: true },
    })

    Object.defineProperties(this, {
        active: { get: getActive, enumerable: true },
        inactive: { get: getInactive, enumerable: true },
    })

    Object.freeze(this.owned)
    Object.freeze(this)
}
