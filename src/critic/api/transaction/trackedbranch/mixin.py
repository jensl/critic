from critic import api
from ..branch import validate_branch_name
from ..item import Insert
from ..modifier import Modifier
from ..utils import requireSystem
from .modify import ModifyTrackedBranch


class ModifyRepository(Modifier[api.repository.Repository]):
    @requireSystem
    async def trackBranch(
        self, url: str, remote_name: str, local_name: str
    ) -> ModifyTrackedBranch:
        # Check if the branch already exists. If it does, its name must be fine.
        # If it doesn't already exist, ensure that the branch name is valid. If
        # not, the tracking will fail to create it either way, so best not set
        # the tracking up at all.
        if await self.subject.is_ready:
            try:
                await self.subject.resolveRef("refs/heads/" + local_name)
            except api.repository.InvalidRef:
                await validate_branch_name(self.subject, local_name)

        delay = api.critic.settings().repositories.branch_update_interval

        self.transaction.wakeup_service("branchtracker")

        return await ModifyTrackedBranch.create(
            self.transaction, self.subject, url, remote_name, local_name, delay
        )

    @requireSystem
    async def trackTags(self, url: str) -> None:
        await self.transaction.execute(
            Insert("trackedbranches").values(
                repository=self.subject,
                local_name="*",
                remote=url,
                remote_name="*",
                forced=True,
                delay=api.critic.settings().repositories.tags_update_interval,
            )
        )

        self.transaction.wakeup_service("branchtracker")
