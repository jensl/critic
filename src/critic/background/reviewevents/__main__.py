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

# type: ignore

from __future__ import annotations

import asyncio
import logging
from typing import Set

logger = logging.getLogger("critic.background.reviewevents")

from .handlebatch import handle_batch
from .handlebranchupdate import handle_branchupdate
from .handlepinged import handle_pinged
from .handlepublished import handle_published
from critic import api
from critic import background
from critic import pubsub


class EventFailed(Exception):
    def __init__(self, event):
        self.event = event


class ReviewEventsService(background.service.BackgroundService):
    name = "reviewevents"
    want_pubsub = True

    __processing = Set[int]

    def __init__(self) -> None:
        super().__init__()
        self.__processing = set()

    async def pubsub_connected(self, client: pubsub.Client) -> None:
        async def handle_message(
            channel: pubsub.ChannelName, message: pubsub.Message
        ) -> None:
            logger.debug("received message: %r", message)
            self.do_wake_up()

        await client.subscribe(pubsub.ChannelName("reviewevents"), handle_message)

        # Wake us up once ASAP, in case something happened while we did not have
        # a connection to the Publish/Subscribe service.
        self.do_wake_up()

    async def handle_event(
        self, critic: api.critic.Critic, event: api.reviewevent.ReviewEvent
    ) -> api.reviewevent.ReviewEvent:
        try:
            logger.debug("Handling event: %s", event)

            if event.type == "created":
                pass
            elif event.type == "published":
                await handle_published(critic, event)
            elif event.type == "branchupdate":
                await handle_branchupdate(critic, event)
            elif event.type == "batch":
                await handle_batch(critic, event)
            elif event.type == "pinged":
                await handle_pinged(critic, event)
            else:
                logger.warning("Unhandled event: %s", event)
        except Exception as error:
            raise EventFailed(event) from error
        else:
            return event

    async def wake_up(self) -> None:
        logger.debug("woke up")

        async with self.start_session() as critic:
            futures = set()

            while True:
                async with api.critic.Query[int](
                    critic,
                    """SELECT id
                         FROM reviewevents
                        WHERE NOT (processed OR failed)""",
                ) as result:
                    pending_event_ids = await result.scalars()

                for event_id in pending_event_ids:
                    if event_id in self.__processing:
                        continue
                    self.__processing.add(event_id)

                    event = await api.reviewevent.fetch(critic, event_id)

                    futures.add(asyncio.create_task(self.handle_event(critic, event)))

                if not futures:
                    break

                done, futures = await asyncio.wait(
                    futures, timeout=3, return_when=asyncio.FIRST_COMPLETED
                )

                updates = []

                for future in done:
                    try:
                        event = future.result()
                        logger.info("Processed event: %s", event)
                        updates.append({"failed": False, "event_id": event.id})
                    except EventFailed as failed:
                        logger.exception("Event failed: %s", failed.event)
                        updates.append({"failed": True, "event_id": event.id})

                if updates:
                    async with critic.transaction() as cursor:
                        await cursor.executemany(
                            """UPDATE reviewevents
                                  SET processed=NOT {failed},
                                      failed={failed}
                                WHERE id={event_id}""",
                            updates,
                        )

        logger.debug("going back to sleep")


if __name__ == "__main__":
    background.service.call(ReviewEventsService)
