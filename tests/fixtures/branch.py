from __future__ import annotations

import pytest

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Protocol

from .api import API
from .websocket import WebSocket
from .instance import User
from .repository import Worktree
from ..utilities import Anonymizer, raise_for_status
from ..utilities.execute import ExecuteResult


class Branch:
    def __init__(
        self,
        websocket: WebSocket,
        anonymizer: Anonymizer,
        worktree: Worktree,
        name: str,
    ):
        self.websocket = websocket
        self.anonymizer = anonymizer
        self.worktree = worktree
        self.name = name
        self.data: Dict[str, Any] = {}

    @property
    def id(self) -> int:
        return self.data["object_id"]

    async def push(self) -> ExecuteResult:
        output = raise_for_status(await self.worktree.push_new())
        self.data = await self.websocket.expect(
            action="created", resource_name="branches", name=self.name
        )
        self.anonymizer.define(BranchId={self.name: self.id})
        return output


class CreateBranch(Protocol):
    @asynccontextmanager
    def __call__(self, worktree: Worktree, name: str) -> AsyncIterator[Branch]:
        ...


@pytest.fixture
def create_branch(websocket: WebSocket, anonymizer: Anonymizer) -> CreateBranch:
    @asynccontextmanager
    async def create_branch(worktree: Worktree, name: str) -> AsyncIterator[Branch]:
        await worktree.checkout("master", create_branch=name)
        yield Branch(websocket, anonymizer, worktree, name)

    return create_branch
