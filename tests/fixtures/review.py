from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging
import pytest
from typing import (
    Any,
    AsyncIterator,
    Collection,
    Dict,
    Literal,
    Optional,
    Protocol,
    TypedDict,
)

logger = logging.getLogger(__name__)

from . import Request
from .api import API, JSONResponse
from .websocket import WebSocket
from .instance import User
from .repository import CriticRepository
from ..utilities import Anonymizer, raise_for_status


class CommentJSON(TypedDict):
    review: int
    type: Literal["issue", "note"]
    text: str


@dataclass
class Branch:
    id: int
    name: str


class Batch(API):
    def __init__(self, session: API, review: Review):
        super().__init__(session.frontend, session.anonymizer)
        self.__review = review
        self.__is_published = False

    async def publish(self, comment: Optional[str] = None) -> JSONResponse:
        payload = {} if comment is None else {"comment": comment}
        self.__is_published = True
        return await self.post(self.__review.path("batches"), payload)

    @property
    def is_published(self) -> bool:
        return self.__is_published


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
        self.data = data["reviews"][0]
        self.id = self.data["id"]
        branch_data = data["linked"]["branches"][0]
        self.branch = Branch(branch_data["id"], branch_data["name"])

    def path(self, suffix: Optional[str] = None) -> str:
        base = f"reviews/{self.id}"
        if suffix:
            return f"{base}/{suffix}"
        return base

    @property
    async def is_ready(self) -> None:
        await self.websocket.expect(
            action="modified",
            resource_name="reviews",
            object_id=self.id,
            updates={"is_ready": True},
        )

    async def publish(self) -> None:
        raise_for_status(
            await self.api.with_session(
                self.owner, lambda api: api.put(self.path(), {"state": "open"})
            )
        )

    async def tags(self, session: API) -> Collection[str]:
        result = raise_for_status(
            await session.get(self.path(), fields="tags", include="reviewtags")
        )
        tag_name = {
            tag["id"]: tag["name"] for tag in result.data["linked"]["reviewtags"]
        }
        return sorted(tag_name[tag_id] for tag_id in result.data["reviews"][0]["tags"])

    def issue(self, text: str) -> CommentJSON:
        return CommentJSON(review=self.id, type="issue", text=text)

    @asynccontextmanager
    async def batch_as(self, user: User) -> AsyncIterator[Batch]:
        async with self.api.session(user) as session:
            batch = Batch(session, self)
            yield batch
            if not batch.is_published:
                await batch.publish()


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
        repository: CriticRepository, owner: User, *, name: Optional[str] = None
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
                        include="branches",
                    ),
                )
            ).data,
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
