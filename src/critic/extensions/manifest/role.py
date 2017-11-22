from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Collection, Dict, Optional, Set

from critic import dbaccess
from critic.extensions import manifest


class Role(ABC):
    role_types: Dict[str, type] = {}
    role_type: ClassVar[str]
    table_names: ClassVar[Set[str]] = set()

    does_execute: bool = True
    description: str
    flavor: str
    entrypoint: Optional[str]

    def __init_subclass__(cls, *, role_type: str):
        assert role_type not in Role.role_types
        Role.role_types[role_type] = cls
        cls.role_type = role_type

    @classmethod
    def tables(cls) -> Collection[str]:
        return {"extensionroles"} | cls.table_names

    def set_execute(self, *, flavor: str, entrypoint: str) -> None:
        self.flavor = flavor
        self.entrypoint = entrypoint

    def set_description(self, description: str) -> None:
        self.description = description

    async def install(
        self, cursor: dbaccess.TransactionCursor, version_id: int
    ) -> None:
        role_id = await dbaccess.Insert[int](
            cursor,
            "extensionroles",
            {
                "version": version_id,
                "description": self.description,
                "flavor": self.flavor,
                "entrypoint": self.entrypoint,
            },
            returning="id",
        )
        await self.install_specific(cursor, role_id)

    @abstractmethod
    async def install_specific(
        self, cursor: dbaccess.TransactionCursor, role_id: int
    ) -> None:
        ...

    def check(self, manifest: manifest.Manifest) -> None:
        self.check_specific(manifest)

    def check_specific(self, manifest: manifest.Manifest) -> None:
        pass
