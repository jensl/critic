import logging
from typing import Dict, Sequence

logger = logging.getLogger(__name__)

from critic.background.differenceengine.protocol import Source
from critic.background.gitaccessor import GitRepositoryProxy
from critic.gitaccess import SHA1, GitBlob
from critic.gitaccess.giterror import GitError
from .decode import decode


async def read_sources(*sources: Source) -> Sequence[str]:
    decoded: Dict[SHA1, str] = {}
    encodings: Dict[SHA1, Sequence[str]] = {
        source.sha1: source.encodings for source in sources
    }
    (repository_path,) = set(source.repository_path for source in sources)

    async with GitRepositoryProxy.make(repository_path) as repository:
        async for sha1, gitobject in repository.fetch(
            *(source.sha1 for source in sources), object_factory=GitBlob
        ):
            if isinstance(gitobject, GitError):
                raise gitobject
            decoded[sha1] = decode(encodings[sha1], gitobject.asBlob().data)

    return [decoded[source.sha1] for source in sources]


async def read_source(source: Source) -> str:
    return (await read_sources(source))[0]
