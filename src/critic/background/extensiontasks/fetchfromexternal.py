import logging

logger = logging.getLogger(__name__)

from .request import Request

from critic import api
from critic import gitaccess


class FetchFromExternal(Request[bool]):
    def __init__(self, extension_id: int):
        self.extension_id = extension_id

    async def dispatch(self, critic: api.critic.Critic) -> bool:
        extension = await api.extension.fetch(critic, self.extension_id)
        logger.info(
            "Updating external extension %s from %s", await extension.key, extension.url
        )
        gitrepository = gitaccess.GitRepository.direct(await extension.path)
        await gitrepository.run("remote", "set-url", "origin", extension.url)
        try:
            await gitrepository.run("fetch", "origin")
        except gitaccess.GitError as error:
            logger.exception("Error fetching from external extension repository")
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


async def fetch_from_external(
    critic: api.critic.Critic, extension: api.extension.Extension
) -> bool:
    return await FetchFromExternal(extension.id).issue()
