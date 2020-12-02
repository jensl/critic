from __future__ import annotations

import logging
from typing import List, Set, cast

logger = logging.getLogger("critic.background.extensiontasks")

from critic import background
from critic import pubsub

from .request import Request


class ExtensionTasks(background.service.BackgroundService):
    name = "extensiontasks"
    want_pubsub = True

    __failed_events: Set[int]

    def will_start(self) -> bool:
        if not self.settings.extensions.enabled:
            logger.info("Extension support not enabled")
            return False
        return True

    async def did_start(self) -> None:
        self.__failed_events = set()

    async def wake_up(self) -> None:
        async with self.start_session() as critic:
            async with critic.query(
                """SELECT id
                     FROM extensionfilterhookevents
                 ORDER BY id ASC"""
            ) as result:
                event_ids = await result.scalars()

            finished_events: List[int] = []

            for event_id in event_ids:
                if event_id not in self.__failed_events:
                    try:
                        # extensions.role.filterhook.processFilterHookEvent(
                        #     critic.database, event_id, self.debug
                        # )
                        raise Exception("not implemented")
                    except Exception:
                        logger.exception("Failed to process filter hook event:")
                        self.__failed_events.add(event_id)
                    else:
                        finished_events.append(event_id)

            async with critic.transaction() as cursor:
                await cursor.execute(
                    """DELETE
                         FROM extensionfilterhookevents
                        WHERE {id=finished_events:array}""",
                    finished_events=finished_events,
                )

    async def pubsub_connected(self, client: pubsub.Client, /) -> None:
        await client.handle_requests(
            pubsub.ChannelName("extensiontasks"), self.handle_request
        )

    async def handle_request(
        self, channel_name: pubsub.ChannelName, request: pubsub.IncomingRequest
    ) -> None:
        await request.notify_delivery()
        assert isinstance(request.payload, Request)
        payload = cast(Request[object], request.payload)
        try:
            async with self.start_session() as critic:
                result = await payload.dispatch(critic)
        except Exception as error:
            logger.exception("Failed to handle request")
            await request.notify_error(str(error))
        else:
            await request.notify_response(result)


if __name__ == "__main__":
    background.service.call(ExtensionTasks)
