from __future__ import annotations

from . import Transaction, Delete, Modifier
from .lazy import LazyAPIObject

from critic import api


class CreatedReviewScope(LazyAPIObject, api_module=api.reviewscope):
    @staticmethod
    def make(transaction: Transaction, name: str) -> CreatedReviewScope:
        return CreatedReviewScope(transaction).insert(name=name)


class ModifyReviewScope(Modifier[api.reviewscope.ReviewScope, CreatedReviewScope]):
    def delete(self) -> None:
        self.transaction.items.append(Delete(self.real))

    @staticmethod
    def create(transaction: Transaction, name: str) -> ModifyReviewScope:
        return ModifyReviewScope(
            transaction, CreatedReviewScope.make(transaction, name)
        )
