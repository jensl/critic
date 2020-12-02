from typing import Optional

from critic import api
from ..base import TransactionBase
from .modify import ModifyChangeset


class Transaction(TransactionBase):
    async def ensureChangeset(
        self,
        from_commit: Optional[api.commit.Commit],
        to_commit: api.commit.Commit,
        *,
        conflicts: bool,
    ) -> ModifyChangeset:
        return await ModifyChangeset.ensure(self, from_commit, to_commit, conflicts)
