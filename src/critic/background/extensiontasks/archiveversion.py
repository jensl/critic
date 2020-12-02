import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from .request import Request

from critic import api
from critic import gitaccess


@dataclass
class ArchiveVersionResult:
    data: bytes

    def __repr__(self) -> str:
        return f"ArchiveVersionResult({len(self.data)} bytes)"


class ArchiveVersion(Request[ArchiveVersionResult]):
    def __init__(self, version_id: int):
        self.version_id = version_id

    async def dispatch(self, critic: api.critic.Critic) -> ArchiveVersionResult:
        version = await api.extensionversion.fetch(critic, self.version_id)
        extension = await version.extension
        gitrepository = gitaccess.GitRepository.direct(await extension.path)
        return ArchiveVersionResult(
            await gitrepository.run("archive", "--format=zip", version.sha1)
        )


async def archive_version(version_id: int) -> ArchiveVersionResult:
    return await ArchiveVersion(version_id).issue()
