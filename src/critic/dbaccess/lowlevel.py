from typing import AsyncContextManager, Optional, Protocol, Sequence

from .types import ExecuteArguments, SQLRow


class LowLevelCursor(Protocol):
    @property
    def rowcount(self) -> int:
        ...

    async def execute(
        self, statement: str, arguments: Optional[ExecuteArguments] = None
    ) -> None:
        ...

    async def fetchall(self) -> Sequence[SQLRow]:
        ...

    async def fetchone(self) -> SQLRow:
        ...


class LowLevelConnection(Protocol):
    @property
    def cursor(self) -> LowLevelCursor:
        ...

    async def begin(self) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def savepoint(self, name: str) -> None:
        ...

    async def rollback_to_savepoint(self, name: str) -> None:
        ...

    async def release_savepoint(self, name: str) -> None:
        ...

    async def close(self) -> None:
        ...


class LowLevelConnectionPool(Protocol):
    def acquire(self) -> AsyncContextManager[LowLevelConnection]:
        ...

    def terminate(self) -> None:
        ...

    async def wait_closed(self) -> None:
        ...
