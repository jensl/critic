from typing import Iterable, Optional

from critic import api
from ..base import TransactionBase
from ..utils import requireSystem
from .modify import ModifyRepository


class Transaction(TransactionBase):
    @requireSystem
    async def createRepository(self, name: str, path: str) -> ModifyRepository:
        return await ModifyRepository.create(self, name, path)

    # FIXME: Should require write-access to the repository.
    def modifyRepository(self, subject: api.repository.Repository) -> ModifyRepository:
        return ModifyRepository(self, subject)
