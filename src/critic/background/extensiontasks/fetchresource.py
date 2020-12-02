import logging
from typing import Optional

logger = logging.getLogger(__name__)

from .request import Request
from critic import api
from critic import gitaccess
from critic.gitaccess import SHA1


class FetchResourceResult:
    def __init__(self, sha1: SHA1, data: bytes) -> None:
        self.sha1 = sha1
        self.data = data


class FetchResource(Request[FetchResourceResult]):
    def __init__(self, extension_id: int, version_id: Optional[int], path: str) -> None:
        self.extension_id = extension_id
        self.version_id = version_id
        self.path = path

    async def dispatch(self, critic: api.critic.Critic) -> FetchResourceResult:
        extension = await api.extension.fetch(critic, self.extension_id)
        extension_path = await extension.path
        if extension_path is None:
            raise Exception("extension not found")
        version_ref: Optional[str]
        if self.version_id is not None:
            version_ref = (
                await api.extensionversion.fetch(critic, self.version_id)
            ).sha1
        else:
            version_ref = "HEAD"
        resource_path = self.path
        async with gitaccess.GitRepository.direct(extension_path) as gitrepository:
            try:
                resource_sha1 = await gitrepository.revparse(
                    f"{version_ref}:{resource_path}"
                )
            except gitaccess.GitError:
                raise Exception("resource not found")
            gitobject = await gitrepository.fetchone(
                resource_sha1, wanted_object_type="blob"
            )
        return FetchResourceResult(resource_sha1, gitobject.asBlob().data)


async def fetch_resource(
    critic: api.critic.Critic,
    extension: api.extension.Extension,
    version: Optional[api.extensionversion.ExtensionVersion],
    path: str,
) -> FetchResourceResult:
    return await FetchResource(
        extension.id, version.id if version else None, path
    ).issue()
