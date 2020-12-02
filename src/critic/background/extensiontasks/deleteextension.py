import logging
import os
import shutil

logger = logging.getLogger(__name__)

from .request import Request
from critic import api


class DeleteExtension(Request[bool]):
    def __init__(self, extension_id: int) -> None:
        self.extension_id = extension_id

    async def dispatch(self, critic: api.critic.Critic) -> bool:
        extension = await api.extension.fetch(critic, self.extension_id)
        path = await extension.path
        if os.path.isdir(path):
            shutil.rmtree(path)
        return True


async def delete_extension(
    critic: api.critic.Critic,
    extension: api.extension.Extension,
) -> bool:
    return await DeleteExtension(extension.id).issue()
