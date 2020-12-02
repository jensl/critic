import logging
import os

logger = logging.getLogger(__name__)

from .request import Request

from critic import api
from critic import gitaccess


class CloneExternal(Request[bool]):
    def __init__(self, extension_id: int):
        self.extension_id = extension_id

    async def dispatch(self, critic: api.critic.Critic) -> bool:
        extension = await api.extension.fetch(critic, self.extension_id)
        logger.info(
            "Cloning external extension %s from %s", await extension.key, extension.url
        )
        path = await extension.path
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        gitrepository = gitaccess.GitRepository.direct(path, allow_missing=True)
        try:
            await gitrepository.clone(extension.url, mirror=True)
        except gitaccess.GitError as error:
            logger.exception("Error cloning external extension repository")
            raise Exception(str(error))
        # low_level = await extension.low_level
        # if not low_level:
        #     raise Exception("Extension is not available")
        # versions = await low_level.getVersions()
        # async with critic.transaction() as cursor:
        #     await low_level.prepareVersion(critic, cursor)
        #     for version_name in versions:
        #         await low_level.prepareVersion(
        #             critic, cursor, version_name=version_name
        #         )
        return True


async def clone_external(
    critic: api.critic.Critic, extension: api.extension.Extension
) -> bool:
    return await CloneExternal(extension.id).issue()
