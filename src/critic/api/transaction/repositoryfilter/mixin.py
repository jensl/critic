from typing import Iterable

from critic import api
from .modify import ModifyRepositoryFilter
from ..modifier import Modifier


class ModifyUser(Modifier[api.user.User]):
    async def createFilter(
        self,
        filter_type: api.repositoryfilter.FilterType,
        repository: api.repository.Repository,
        path: str,
        default_scope: bool,
        scopes: Iterable[api.reviewscope.ReviewScope],
        delegates: Iterable[api.user.User],
    ) -> ModifyRepositoryFilter:
        return await ModifyRepositoryFilter.create(
            self.transaction,
            self.subject,
            filter_type,
            repository,
            path,
            default_scope,
            scopes,
            delegates,
        )

    async def modifyFilter(
        self, repository_filter: api.repositoryfilter.RepositoryFilter
    ) -> ModifyRepositoryFilter:
        if await repository_filter.subject != self.subject:
            raise api.user.Error(
                "Cannot modify repository filter belonging to another user"
            )
        return ModifyRepositoryFilter(self.transaction, repository_filter)
