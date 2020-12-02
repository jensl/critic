from typing import Any, Iterable, Optional, Protocol, Tuple


class DatabaseCursor(Protocol):
    def execute(self, sql: str, args: Optional[Tuple[Any, ...]] = None) -> None:
        ...

    def executemany(self, sql: str, args: Iterable[Tuple[Any, ...]]) -> None:
        ...

    def fetchone(self) -> Optional[Tuple[Any, ...]]:
        ...


class DatabaseConnection(Protocol):
    autocommit: bool

    def cursor(self) -> DatabaseCursor:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...

    def close(self) -> None:
        ...
