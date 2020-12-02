from typing import Any

from critic import api
from ..modifier import Modifier
from ..utils import requireAdministrator
from .modify import ModifyRepositorySetting
from . import validate_scope, validate_name


class ModifyRepository(Modifier[api.repository.Repository]):
    @requireAdministrator
    async def defineSetting(
        self, scope: str, name: str, value: Any
    ) -> ModifyRepositorySetting:
        validate_scope(scope)
        validate_name(name)

        try:
            await api.repositorysetting.fetch(
                self.critic, repository=self.subject, scope=scope, name=name
            )
        except api.repositorysetting.NotDefined:
            pass
        else:
            raise api.repositorysetting.Error(
                f"Repository setting already defined: {scope}:{name}"
            )

        return await ModifyRepositorySetting.create(
            self.transaction, self.subject, scope, name, value
        )

    @requireAdministrator
    def modifySetting(
        self, setting: api.repositorysetting.RepositorySetting
    ) -> ModifyRepositorySetting:
        return ModifyRepositorySetting(self.transaction, setting)
