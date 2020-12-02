from typing import Any

from critic import api
from ..modifier import Modifier
from ..utils import requireAdministrator
from . import validate_scope, validate_name
from .modify import ModifyBranchSetting


class ModifyBranch(Modifier[api.branch.Branch]):
    @requireAdministrator
    async def defineSetting(
        self, scope: str, name: str, value: Any
    ) -> ModifyBranchSetting:
        validate_scope(scope)
        validate_name(name)

        try:
            await api.branchsetting.fetch(
                self.critic, branch=self.subject, scope=scope, name=name
            )
        except api.branchsetting.NotDefined:
            pass
        else:
            raise api.branchsetting.Error(
                f"Branch setting already defined: {scope}:{name}"
            )

        return await ModifyBranchSetting.create(
            self.transaction, self.subject, scope, name, value
        )

    @requireAdministrator
    def modifySetting(
        self, setting: api.branchsetting.BranchSetting
    ) -> ModifyBranchSetting:
        return ModifyBranchSetting(self.transaction, setting)
