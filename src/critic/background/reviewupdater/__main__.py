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

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Dict, List, Mapping, Set, Tuple

from critic import dbaccess

logger = logging.getLogger("critic.background.reviewupdater")

from critic import api
from critic import background
from critic import pubsub

from .processreviewbranchupdate import process_review_branch_update
from .processtargetbranchupdate import process_target_branch_update
from .processinitialcommits import process_initial_commits
from .processintegrationrequest import process_integration_request
from ..service import BackgroundService


class ReviewUpdater(BackgroundService):
    name = "reviewupdater"
    want_pubsub = True

    __processing_branchupdates: Set[int]
    __processing_initial_commits: Set[int]
    __processing_integration_requests: Set[int]
    __processing_target_branchupdate: Dict[int, Tuple[int, "asyncio.Future[None]"]]

    def __init__(self) -> None:
        super(ReviewUpdater, self).__init__()
        self.__processing_branchupdates = set()
        self.__processing_initial_commits = set()
        self.__processing_integration_requests = set()
        self.__processing_target_branchupdate = {}

    async def pubsub_connected(self, client: pubsub.Client, /) -> None:
        async def handle_message(
            channel: pubsub.ChannelName, message: pubsub.Message
        ) -> None:
            logger.debug("received message: %r", message)
            self.do_wake_up()

        await client.subscribe(pubsub.ChannelName("branchupdates"), handle_message)
        await client.subscribe(
            pubsub.ChannelName("reviewintegrationrequests"), handle_message
        )

        # Wake us up once ASAP, in case something happened while we did not have
        # a connection to the Publish/Subscribe service.
        self.do_wake_up()

    async def process_review_branchupdate(
        self, review_id: int, branchupdate_id: int, pendingrefupdate_id: int
    ) -> None:
        """Process update of review branch."""
        async with self.start_session() as critic:
            review = await api.review.fetch(critic, review_id)
            branchupdate = await api.branchupdate.fetch(critic, branchupdate_id)

            try:
                await process_review_branch_update(
                    review, branchupdate, pendingrefupdate_id
                )
            except Exception:
                logger.exception(
                    "Failed to process review branch update: r/%d", review_id
                )
            else:
                logger.info("Processed review branch update: r/%d", review_id)
                self.__processing_branchupdates.remove(branchupdate_id)

    async def process_initial_commits(self, review_id: int) -> None:
        """Process the initial commits in a newly created review."""
        async with self.start_session() as critic:
            review = await api.review.fetch(critic, review_id)

            try:
                await process_initial_commits(review)
            except Exception:
                logger.exception("Failed to process initial commits: r/%d", review_id)
            else:
                logger.info("Processed initial commits: r/%d", review_id)
                self.__processing_initial_commits.remove(review_id)

    async def process_integration_request(
        self, review_id: int, request_id: int
    ) -> None:
        """Process an integration request (i.e. try to integrate the review.)"""
        async with self.start_session() as critic:
            review = await api.review.fetch(critic, review_id)

            try:
                await process_integration_request(review, request_id)
            except Exception:
                logger.exception(
                    "Failed to process integration request: r/%d", review_id
                )
            else:
                logger.info("Processed integration request: r/%d", review_id)
                self.__processing_integration_requests.remove(review_id)

    async def process_target_branchupdate(
        self, review_id: int, branchupdate_id: int
    ) -> None:
        """Process an update of a review's target branch."""
        async with self.start_session() as critic:
            review = await api.review.fetch(critic, review_id)
            branchupdate = await api.branchupdate.fetch(critic, branchupdate_id)

            async def publish(
                cursor: dbaccess.TransactionCursor, updates: Mapping[str, Any]
            ) -> None:
                pubsub_client = await self.pubsub_client
                await pubsub_client.publish(
                    cursor,
                    pubsub.PublishMessage(
                        pubsub.ChannelName(f"reviews/{review_id}"),
                        pubsub.Payload(
                            {
                                "scope": "reviews",
                                "action": "updated",
                                "id": review_id,
                                "updates": updates,
                            }
                        ),
                    ),
                )

            try:
                await process_target_branch_update(review, branchupdate, publish)
            except Exception:
                logger.exception(
                    "Failed to process target branch update: r/%d", review_id
                )
            else:
                logger.info("Processed target branch update: r/%d", review_id)

    async def wake_up(self) -> None:
        logger.debug("woke up")

        async with self.start_session() as critic:
            tasks: List["asyncio.Future[None]"] = []

            def add_task(coroutine: Awaitable[None]) -> "asyncio.Future[None]":
                task = asyncio.ensure_future(coroutine)
                tasks.append(task)
                return task

            while True:
                async with critic.query(
                    """SELECT r.id AS review_id,
                              bu.id AS branchupdate_id,
                              pru.id AS pendingrefupdate_id
                         FROM branchupdates AS bu
                         JOIN branches AS b ON (b.id=bu.branch)
                         JOIN reviews AS r ON (r.branch=b.id)
              LEFT OUTER JOIN reviewupdates AS ru ON (ru.branchupdate=bu.id)
              LEFT OUTER JOIN pendingrefupdates AS pru ON (
                                pru.repository=b.repository AND
                                pru.name=('refs/heads/' || b.name)
                              )
                        WHERE ru.event IS NULL
                          AND (pru.id IS NULL OR
                               pru.state='processed')"""
                ) as result:
                    async for (
                        review_id,
                        branchupdate_id,
                        pendingrefupdate_id,
                    ) in result:
                        if branchupdate_id not in self.__processing_branchupdates:
                            logger.debug(
                                "Processing update: r/%d (branchupdate=%d) ...",
                                review_id,
                                branchupdate_id,
                            )

                            self.__processing_branchupdates.add(branchupdate_id)

                            add_task(
                                self.process_review_branchupdate(
                                    review_id, branchupdate_id, pendingrefupdate_id
                                )
                            )

                initial_commits: Dict[int, Set[int]] = defaultdict(set)

                async with critic.query(
                    """SELECT reviewcommits.review, reviewcommits.commit
                         FROM reviews
                         JOIN reviewcommits ON (
                                reviewcommits.review=reviews.id
                              )
              LEFT OUTER JOIN reviewchangesets USING (review)
              LEFT OUTER JOIN changesets ON (
                                changesets.id=reviewchangesets.changeset AND
                                changesets.to_commit=reviewcommits.commit
                              )
                        WHERE reviews.state='draft'
                          AND reviewchangesets.review IS NULL"""
                ) as result:
                    async for review_id, commit_id in result:
                        initial_commits[review_id].add(commit_id)

                for review_id, commit_ids in initial_commits.items():
                    if review_id not in self.__processing_initial_commits:
                        logger.debug(
                            "Processing review: r/%d (%d initial commits) ..."
                            % (review_id, len(commit_ids))
                        )

                        self.__processing_initial_commits.add(review_id)

                        add_task(self.process_initial_commits(review_id))

                async with critic.query(
                    """SELECT id, review
                         FROM reviewintegrationrequests
                        WHERE successful IS NULL AND (
                                (do_squash AND NOT squashed) OR
                                (do_autosquash AND NOT autosquashed) OR
                                (do_integrate AND strategy_used IS NULL)
                              )"""
                ) as result:
                    async for integration_id, review_id in result:
                        self.__processing_integration_requests.add(review_id)

                        add_task(
                            self.process_integration_request(review_id, integration_id)
                        )

                pending_target_branchupdates = []

                async with critic.query(
                    """SELECT reviews.id, reviews.integration_branchupdate,
                              MAX(branchupdates.id)
                         FROM reviews
                         JOIN branchupdates ON (
                                branchupdates.branch=reviews.integration_target
                              )
                        WHERE NOT reviews.integration_performed
                          AND reviews.state IN ('draft', 'open')
                     GROUP BY reviews.id"""
                ) as result:
                    async for (
                        review_id,
                        checked_branchupdate_id,
                        current_branchupdate_id,
                    ) in result:
                        if checked_branchupdate_id != current_branchupdate_id:
                            pending_target_branchupdates.append(
                                (review_id, current_branchupdate_id)
                            )

                for review_id, branchupdate_id in pending_target_branchupdates:
                    if review_id in self.__processing_target_branchupdate:
                        (
                            processing_branchupdate_id,
                            task,
                        ) = self.__processing_target_branchupdate[review_id]

                        if processing_branchupdate_id == branchupdate_id:
                            continue

                        task.cancel()

                    task = add_task(
                        self.process_target_branchupdate(review_id, branchupdate_id)
                    )

                    self.__processing_target_branchupdate[review_id] = (
                        branchupdate_id,
                        task,
                    )

                if not tasks:
                    logger.debug("no active tasks")
                    break

                logger.debug("waiting for %d tasks to finish", len(tasks))
                done, pending = await asyncio.wait(tasks, timeout=1)

                for task in done:
                    try:
                        task.result()
                    except Exception:
                        logger.exception("Task failed!")

                if not pending:
                    logger.debug("all tasks finished")
                    break

                tasks[:] = pending

        logger.debug("going back to sleep")


if __name__ == "__main__":
    background.service.call(ReviewUpdater)
