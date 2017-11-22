from __future__ import annotations

import pytest

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Protocol

from . import Request
from .api import API
from .websocket import WebSocket
from .instance import User
from .repository import CriticRepository
from ..utilities import Anonymizer, raise_for_status


class Review:
    def __init__(
        self,
        api: API,
        websocket: WebSocket,
        owner: User,
        anonymizer: Anonymizer,
        data: Dict[str, Any],
    ):
        self.api = api
        self.websocket = websocket
        self.owner = owner
        self.anonymizer = anonymizer
        self.data = data
        self.id = data["id"]
        self.branch_id = data["branch"]

    def path(self, suffix: str = None) -> str:
        base = f"reviews/{self.id}"
        if suffix:
            return f"{base}/{suffix}"
        return base

    @property
    async def is_ready(self) -> None:
        await self.websocket.expect(
            action="created",
            resource_name="reviewevents",
            review_id=self.id,
            event_type="ready",
        )

    async def publish(self) -> None:
        raise_for_status(
            await self.api.with_session(
                self.owner, lambda api: api.put(self.path(), {"state": "open"})
            )
        )


class CreateReview(Protocol):
    @asynccontextmanager
    def __call__(
        self, repository: CriticRepository, owner: User
    ) -> AsyncIterator[Review]:
        ...


@pytest.fixture
def create_review(
    request: Request,
    api: API,
    websocket: WebSocket,
    admin: User,
    anonymizer: Anonymizer,
) -> CreateReview:
    @asynccontextmanager
    async def create_review(
        repository: CriticRepository, owner: User, *, name: str = None
    ) -> AsyncIterator[Review]:
        if name is None:
            name = request.node.name

        branch_id = raise_for_status(
            await api.get(f"repositories/{repository.id}/branches", created_by=owner.id)
        ).data["branches"][0]["id"]

        commits = raise_for_status(await api.get(f"branches/{branch_id}/commits")).data[
            "commits"
        ]

        review = Review(
            api,
            websocket,
            owner,
            anonymizer,
            raise_for_status(
                await api.with_session(
                    owner,
                    lambda api: api.post(
                        "reviews",
                        {
                            "repository": repository.id,
                            "branch": f"r/{name}",
                            "commits": [commit["id"] for commit in commits],
                        },
                    ),
                )
            ).data["reviews"][0],
        )
        anonymizer.define(ReviewId={name: review.id})

        await review.is_ready

        try:
            yield review
        finally:
            raise_for_status(
                await api.with_session(
                    admin, lambda api: api.delete(f"reviews/{review.id}")
                )
            )

    return create_review
